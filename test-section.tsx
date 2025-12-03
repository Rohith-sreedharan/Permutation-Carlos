      {simulation && (
        <div className="mb-6 p-6 bg-gradient-to-br from-purple-900/20 via-navy/40 to-electric-blue/20 rounded-xl border border-purple-500/30 relative overflow-hidden shadow-xl shadow-purple-500/10">
          <div className="absolute top-0 right-0 w-32 h-32 bg-electric-blue/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-8 -left-8 w-24 h-24 bg-gold/5 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <div className="text-3xl">{edgeValidation.classification === 'EDGE' ? '🎯' : edgeValidation.classification === 'LEAN' ? '⚡' : '✅'}</div>
                  <div>
                    <h3 className={`text-2xl font-bold font-teko leading-none ${
                      edgeValidation.classification === 'EDGE' ? 'text-neon-green' :
                      edgeValidation.classification === 'LEAN' ? 'text-gold' :
                      'text-electric-blue'
                    }`}>
                      {edgeValidation.classification === 'EDGE' ? 'BEATVEGAS EDGE DETECTED' :
                       edgeValidation.classification === 'LEAN' ? 'MODERATE LEAN IDENTIFIED' :
                       'MARKET ALIGNED - NO EDGE'}
                    </h3>
                    <p className="text-xs text-light-gray mt-1">
                      {edgeValidation.classification === 'EDGE' ? 'High-Conviction Quantitative Signal' :
                       edgeValidation.classification === 'LEAN' ? 'Soft Edge - Proceed with Caution' :
                       'Model-Market Consensus Detected'}
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-4 gap-4 mt-4">
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">Edge Classification</div>
                    <div className={`text-3xl font-black font-teko ${
                      edgeValidation.classification === 'EDGE' ? 'text-neon-green' :
                      edgeValidation.classification === 'LEAN' ? 'text-gold' :
                      'text-electric-blue'
                    }`}>
                      {edgeValidation.classification}
                    </div>
                    <div className={`text-xs font-semibold mt-1 ${
                      edgeValidation.classification === 'LEAN' ? 'text-gold/80' : 'text-light-gray/60'
                    }`}>
                      {edgeValidation.classification === 'LEAN' ? 'Soft edge — proceed cautious' : `${edgeValidation.passed_rules}/${edgeValidation.total_rules} rules passed`}
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20 relative group">
                    <div className="text-xs text-light-gray mb-1">Model Spread</div>
                    <div className="text-2xl font-bold text-electric-blue font-teko">
                      {((simulation.team_a_win_probability || simulation.win_probability || 0.5) > 0.5 ? '-' : '+')}{Math.abs((simulation.projected_score || 220) - (simulation.vegas_line || 220)).toFixed(1)}
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">vs market</div>
                    {/* Critical Disclaimer Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-56 p-3 bg-bold-red/95 border-2 border-bold-red rounded-lg shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10">
                      <p className="text-xs text-white font-semibold leading-relaxed">
                        ⚠️ This is model vs book deviation, NOT a betting pick. Do not bet based on this number alone.
                      </p>
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">CLV Prediction</div>
                    <div className="text-2xl font-bold text-neon-green font-teko">
                      {clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)}%
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">
                      {clvPrediction.confidence} confidence
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">Total Deviation</div>
                    <div className="text-2xl font-bold text-electric-blue font-teko">
                      +{Math.abs((simulation.projected_score || 220) - (simulation.vegas_line || 220)).toFixed(1)} pts
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">model vs book</div>
                  </div>
                </div>
                
                {/* Edge Validation Warnings */}
                {edgeValidation.failed_rules.length > 0 && (
                  <div className="mt-3 p-3 bg-bold-red/10 border border-bold-red/30 rounded-lg">
                    <div className="text-xs font-bold text-bold-red mb-2">⚠️ Edge Quality Warnings:</div>
                    <ul className="text-xs text-light-gray space-y-1">
                      {edgeValidation.failed_rules.map((rule, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-bold-red">•</span>
                          <span>{rule}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                <details className="mt-4 cursor-pointer group">
                  <summary className="text-xs font-bold text-white uppercase tracking-wide list-none flex items-center gap-2 hover:text-gold transition">
                    <span className="transform group-open:rotate-90 transition-transform">▶</span>
                    Edge Summary
                  </summary>
                  <div className="mt-3 text-xs text-light-gray/80 leading-relaxed pl-4 border-l-2 border-gold/30">
                    {edgeValidation.summary}
                    <br /><br />
                    Expected line movement: <strong className="text-gold">{clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)} points</strong> by kickoff
                  </div>
                </details>
                
                {/* CLV Prediction Details */}
                <div className="mt-3 p-3 bg-navy/30 rounded-lg border border-electric-blue/20">
                  <div className="text-xs font-bold text-electric-blue mb-2">📈 Closing Line Value (CLV) Forecast</div>
                  <div className="text-xs text-light-gray leading-relaxed">
                    {clvPrediction.reasoning}
                  </div>
                  <div className="text-xs text-gold mt-2">
                    Expected line movement: <strong>{clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)} points</strong> by kickoff
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Sharp Analysis - Model vs Market */}
      {simulation?.sharp_analysis && (simulation.sharp_analysis.total?.has_edge || simulation.sharp_analysis.spread?.has_edge) ? (
        <div className="mb-6 p-6 bg-gradient-to-br from-purple-900/30 to-blue-900/30 rounded-xl border-2 border-purple-500/50 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="text-4xl">🎯</div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-purple-300 mb-2 font-teko">SHARP SIDE DETECTED</h3>
              
              {/* CRITICAL DISCLAIMER */}
              <div className="mb-4 p-3 bg-bold-red/20 border-2 border-bold-red/60 rounded-lg">
                <p className="text-xs text-bold-red font-bold flex items-center gap-2">
                  <span className="text-base">⚠️</span>
                  <span>Sharp Side = model mispricing detection, NOT a betting recommendation. This platform provides statistical analysis only.</span>
                </p>
              </div>
              
              {/* Total Analysis */
              {simulation.sharp_analysis.total?.has_edge && (
                <div className="mb-4 p-4 bg-charcoal/50 rounded-lg border border-purple-500/30">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                        simulation.sharp_analysis.total.edge_grade === 'S' ? 'bg-purple-600 text-white' :
                        simulation.sharp_analysis.total.edge_grade === 'A' ? 'bg-green-600 text-white' :
                        simulation.sharp_analysis.total.edge_grade === 'B' ? 'bg-blue-600 text-white' :
                        'bg-yellow-600 text-black'
                      }`}>
                        {simulation.sharp_analysis.total.edge_grade} GRADE
                      </div>
                      <div className="text-lg font-bold text-white">
                        {simulation.sharp_analysis.total.sharp_side_display}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-400">Edge</div>
                      <div className="text-lg font-bold text-purple-300">
                        {simulation.sharp_analysis.total.edge_points?.toFixed(1)} pts
                      </div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">Vegas Line</div>
                      <div className="text-base font-bold text-white">
                        O/U {simulation.sharp_analysis.total.vegas_total}
                      </div>
                    </div>
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">BeatVegas Model</div>
                      <div className="text-base font-bold text-purple-300">
                        {simulation.sharp_analysis.total.model_total?.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  
                  {/* Edge Reasoning */}
                  {simulation.sharp_analysis.total.edge_reasoning && (
                    <div className="mt-4 p-4 bg-purple-900/20 rounded-lg border-l-4 border-purple-500">
                      <div className="text-xs font-bold text-purple-300 mb-2">
                        🔍 Why Our Model Found Edge on {simulation.sharp_analysis.total.edge_direction} {simulation.sharp_analysis.total.vegas_total}:
                      </div>
                      
                      <div className="text-sm text-gray-300 mb-3 leading-relaxed">
                        {simulation.sharp_analysis.total.edge_reasoning.model_reasoning}
                      </div>
                      
                      <div className="text-xs font-bold text-purple-300 mb-2">Primary Factor:</div>
                      <div className="text-sm text-white mb-3">
                        {simulation.sharp_analysis.total.edge_reasoning.primary_factor}
                      </div>
                      
                      {simulation.sharp_analysis.total.edge_reasoning.contributing_factors?.length > 0 && (
                        <>
                          <div className="text-xs font-bold text-purple-300 mb-2">Contributing Factors:</div>
                          <div className="space-y-1 mb-3">
                            {simulation.sharp_analysis.total.edge_reasoning.contributing_factors.map((factor, idx) => (
                              <div key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                                <span className="text-purple-400">•</span>
                                <span>{factor}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                      
                      <div className="text-xs text-gray-400 italic mt-3 p-2 bg-charcoal/50 rounded">
                        {simulation.sharp_analysis.total.edge_reasoning.market_positioning}
                      </div>
                      
                      {simulation.sharp_analysis.total.edge_reasoning.contrarian_indicator && (
                        <div className="mt-3 flex items-center gap-2 text-xs font-bold text-yellow-400">
                          <span>⚠️</span>
                          <span>CONTRARIAN POSITION - Model diverges significantly from market consensus</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-3 text-xs text-gray-500 italic">
                    {simulation.sharp_analysis.disclaimer}
                  </div>
                </div>
              )}
              
              {/* Spread Analysis (if exists) */}
              {simulation.sharp_analysis.spread?.has_edge && (
                <div className="p-4 bg-charcoal/50 rounded-lg border border-purple-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                      simulation.sharp_analysis.spread.edge_grade === 'S' ? 'bg-purple-600 text-white' :
                      simulation.sharp_analysis.spread.edge_grade === 'A' ? 'bg-green-600 text-white' :
                      'bg-blue-600 text-white'
                    }`}>
                      {simulation.sharp_analysis.spread.edge_grade} GRADE
                    </div>
                    <div className="text-lg font-bold text-white">
                      {simulation.sharp_analysis.spread.sharp_side_display}
                    </div>
                    <div className="text-sm text-purple-300">
                      ({simulation.sharp_analysis.spread.edge_points?.toFixed(1)} pt edge)
                    </div>
                  </div>
                  <div className="text-sm text-gray-300 mt-2">
                    {simulation.sharp_analysis.spread.sharp_side_reason}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
