/**
 * Frontend Logging Utility
 * Sends logs to backend for admin panel monitoring
 */

import { API_BASE_URL } from '../services/api';

type LogLevel = 'info' | 'warning' | 'error';

interface LogData {
  level: LogLevel;
  message: string;
  details?: any;
  url?: string;
  userAgent?: string;
}

class FrontendLogger {
  private static instance: FrontendLogger;
  private queue: LogData[] = [];
  private flushInterval: number = 5000; // 5 seconds
  private maxQueueSize: number = 50;

  private constructor() {
    // Flush queue periodically
    setInterval(() => this.flush(), this.flushInterval);

    // Flush on page unload
    window.addEventListener('beforeunload', () => this.flush());

    // Catch unhandled errors
    window.addEventListener('error', (event) => {
      this.error('Unhandled error', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error?.stack,
      });
    });

    // Catch unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.error('Unhandled promise rejection', {
        reason: event.reason,
        promise: event.promise,
      });
    });
  }

  public static getInstance(): FrontendLogger {
    if (!FrontendLogger.instance) {
      FrontendLogger.instance = new FrontendLogger();
    }
    return FrontendLogger.instance;
  }

  private log(level: LogLevel, message: string, details?: any) {
    // Also log to console
    const consoleMethod = level === 'error' ? console.error : level === 'warning' ? console.warn : console.log;
    consoleMethod(`[${level.toUpperCase()}]`, message, details);

    // Add to queue
    this.queue.push({
      level,
      message,
      details,
      url: window.location.href,
      userAgent: navigator.userAgent,
    });

    // Flush if queue is full
    if (this.queue.length >= this.maxQueueSize) {
      this.flush();
    }
  }

  public info(message: string, details?: any) {
    this.log('info', message, details);
  }

  public warning(message: string, details?: any) {
    this.log('warning', message, details);
  }

  public error(message: string, details?: any) {
    this.log('error', message, details);
  }

  private async flush() {
    if (this.queue.length === 0) return;

    const logs = [...this.queue];
    this.queue = [];

    try {
      const token = localStorage.getItem('token');
      
      // Send logs in batch
      await fetch(`${API_BASE_URL}/api/admin/panel/frontend-logs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        body: JSON.stringify({
          logs: logs,
          batch: true,
        }),
      });
    } catch (error) {
      // Don't log errors from logging to avoid infinite loops
      console.error('Failed to send logs to backend:', error);
      
      // Re-add logs to queue to retry later
      this.queue.unshift(...logs);
      
      // Limit queue size to prevent memory issues
      if (this.queue.length > this.maxQueueSize * 2) {
        this.queue = this.queue.slice(0, this.maxQueueSize);
      }
    }
  }

  /**
   * Track user actions for analytics
   */
  public trackAction(action: string, details?: any) {
    this.info(`User action: ${action}`, details);
  }

  /**
   * Track API errors
   */
  public trackAPIError(endpoint: string, error: any, response?: any) {
    this.error(`API Error: ${endpoint}`, {
      error: error.message || error,
      response,
      endpoint,
    });
  }

  /**
   * Track performance metrics
   */
  public trackPerformance(metric: string, value: number, details?: any) {
    this.info(`Performance: ${metric}`, {
      value,
      ...details,
    });
  }

  /**
   * Track page views
   */
  public trackPageView(page: string) {
    this.info(`Page view: ${page}`, {
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
    });
  }
}

// Export singleton instance
export const logger = FrontendLogger.getInstance();

// Export for easy imports
export default logger;

// Example usage:
/*
import logger from './logger';

// Log info
logger.info('User logged in', { userId: '123' });

// Log warning
logger.warning('Rate limit approaching', { remaining: 10 });

// Log error
logger.error('Failed to load data', { error: errorMessage });

// Track user actions
logger.trackAction('button_click', { button: 'generate_parlay' });

// Track API errors
logger.trackAPIError('/api/predictions', error, response);

// Track performance
logger.trackPerformance('page_load_time', 1234);

// Track page views
logger.trackPageView('/dashboard');
*/
