/**
 * Snapshot Mismatch Detection & Integrity Logging
 * 
 * Detects when simulation data has inconsistent snapshot_hash values
 * and logs comprehensive debug information for troubleshooting.
 */

interface LogViolation {
  event_id: string;
  market_type: string;
  expected_selection_id: string;
  received_selection_id: string;
  snapshot_hash_values: {
    main: string;
    home_selection?: string;
    away_selection?: string;
    model_preference?: string;
  };
  full_payload: any;
  timestamp: string;
  user_agent: string;
  url: string;
}

class IntegrityLogger {
  private static violations: LogViolation[] = [];
  private static readonly MAX_VIOLATIONS = 100;
  
  /**
   * Log a snapshot mismatch violation
   */
  static logSnapshotMismatch(violation: Omit<LogViolation, 'timestamp' | 'user_agent' | 'url'>): void {
    const fullViolation: LogViolation = {
      ...violation,
      timestamp: new Date().toISOString(),
      user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
      url: typeof window !== 'undefined' ? window.location.href : 'unknown'
    };
    
    // Store violation
    this.violations.push(fullViolation);
    
    // Keep only recent violations
    if (this.violations.length > this.MAX_VIOLATIONS) {
      this.violations.shift();
    }
    
    // Console error with full details
    console.error('🚨 SNAPSHOT MISMATCH DETECTED', {
      event_id: fullViolation.event_id,
      market_type: fullViolation.market_type,
      expected_selection_id: fullViolation.expected_selection_id,
      received_selection_id: fullViolation.received_selection_id,
      snapshot_hash_values: fullViolation.snapshot_hash_values,
      timestamp: fullViolation.timestamp
    });
    
    // Full payload in collapsed group
    console.groupCollapsed('📦 Full Payload (click to expand)');
    console.log(JSON.stringify(fullViolation.full_payload, null, 2));
    console.groupEnd();
    
    // Send to backend logging service (if available)
    this.sendToBackend(fullViolation);
  }
  
  /**
   * Log selection_id mismatch violation
   */
  static logSelectionMismatch(
    event_id: string,
    market_type: string,
    expected_selection_id: string,
    received_selection_id: string,
    payload: any
  ): void {
    this.logSnapshotMismatch({
      event_id,
      market_type,
      expected_selection_id,
      received_selection_id,
      snapshot_hash_values: {
        main: payload.snapshot_hash || 'MISSING'
      },
      full_payload: payload
    });
  }
  
  /**
   * Send violation to backend for persistent logging
   */
  private static async sendToBackend(violation: LogViolation): Promise<void> {
    try {
      // Only in production/staging
      if (process.env.NODE_ENV === 'development') {
        return;
      }
      
      await fetch('/api/logging/integrity-violation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(violation)
      });
    } catch (error) {
      console.warn('Failed to send integrity violation to backend:', error);
    }
  }
  
  /**
   * Get all logged violations
   */
  static getViolations(): LogViolation[] {
    return [...this.violations];
  }
  
  /**
   * Clear all violations
   */
  static clearViolations(): void {
    this.violations = [];
  }
  
  /**
   * Export violations as JSON
   */
  static exportViolations(): string {
    return JSON.stringify(this.violations, null, 2);
  }
}

/**
 * Validate snapshot consistency across simulation data
 */
export function validateSnapshotConsistency(simulation: any): {
  valid: boolean;
  errors: string[];
  warnings: string[];
} {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  if (!simulation) {
    errors.push('Simulation data is null or undefined');
    return { valid: false, errors, warnings };
  }
  
  const mainSnapshotHash = simulation.snapshot_hash;
  
  if (!mainSnapshotHash) {
    errors.push('Main snapshot_hash is missing');
  }
  
  // Check sharp_analysis markets
  const sharpAnalysis = simulation.sharp_analysis;
  
  if (sharpAnalysis) {
    // Spread market
    if (sharpAnalysis.spread) {
      const spreadHash = sharpAnalysis.spread.snapshot_hash;
      if (spreadHash && spreadHash !== mainSnapshotHash) {
        errors.push(`Spread snapshot_hash mismatch: main=${mainSnapshotHash}, spread=${spreadHash}`);
      }
    }
    
    // Moneyline market
    if (sharpAnalysis.moneyline) {
      const mlHash = sharpAnalysis.moneyline.snapshot_hash;
      if (mlHash && mlHash !== mainSnapshotHash) {
        errors.push(`Moneyline snapshot_hash mismatch: main=${mainSnapshotHash}, ml=${mlHash}`);
      }
    }
    
    // Total market
    if (sharpAnalysis.total) {
      const totalHash = sharpAnalysis.total.snapshot_hash;
      if (totalHash && totalHash !== mainSnapshotHash) {
        errors.push(`Total snapshot_hash mismatch: main=${mainSnapshotHash}, total=${totalHash}`);
      }
    }
  }
  
  return {
    valid: errors.length === 0,
    errors,
    warnings
  };
}

/**
 * Validate model preference matches probability tiles
 */
export function validateModelPreference(
  homeSelectionId: string,
  awaySelectionId: string,
  modelPreferenceSelectionId: string,
  homeProbability: number,
  awayProbability: number
): {
  valid: boolean;
  error?: string;
} {
  // Preference MUST match one of the selection_ids
  if (modelPreferenceSelectionId !== homeSelectionId && 
      modelPreferenceSelectionId !== awaySelectionId) {
    return {
      valid: false,
      error: `Model preference selection_id (${modelPreferenceSelectionId}) doesn't match home (${homeSelectionId}) or away (${awaySelectionId})`
    };
  }
  
  // Preference probability should align (within tolerance)
  const isHomePreference = modelPreferenceSelectionId === homeSelectionId;
  const expectedProb = isHomePreference ? homeProbability : awayProbability;
  
  // This is a warning, not an error (backend might have EV-based preference)
  if (isHomePreference && homeProbability < awayProbability) {
    console.warn(`Model prefers home despite lower probability: home=${homeProbability}, away=${awayProbability}`);
  }
  if (!isHomePreference && awayProbability < homeProbability) {
    console.warn(`Model prefers away despite lower probability: home=${homeProbability}, away=${awayProbability}`);
  }
  
  return { valid: true };
}

/**
 * Auto-refetch hook when mismatch detected
 */
export async function handleSnapshotMismatch(
  event_id: string,
  market_type: string,
  refetchFn: () => Promise<any>
): Promise<any> {
  console.warn(`🔄 Snapshot mismatch detected for ${event_id} (${market_type}). Auto-refetching...`);
  
  // Wait 500ms before refetch (avoid race condition)
  await new Promise(resolve => setTimeout(resolve, 500));
  
  try {
    const freshData = await refetchFn();
    
    // Validate fresh data
    const validation = validateSnapshotConsistency(freshData);
    
    if (!validation.valid) {
      console.error(`❌ Refetch still has integrity issues:`, validation.errors);
      
      // Log the persistent violation
      IntegrityLogger.logSnapshotMismatch({
        event_id,
        market_type,
        expected_selection_id: 'N/A',
        received_selection_id: 'N/A',
        snapshot_hash_values: {
          main: freshData.snapshot_hash || 'MISSING'
        },
        full_payload: freshData
      });
      
      throw new Error('Persistent snapshot inconsistency after refetch');
    }
    
    console.log(`✅ Refetch successful. Data is now consistent.`);
    return freshData;
    
  } catch (error) {
    console.error(`❌ Refetch failed:`, error);
    throw error;
  }
}

export { IntegrityLogger };
export type { LogViolation };
