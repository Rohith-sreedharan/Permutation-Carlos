const Test = () => {
  const simulation: any = {};
  
  return (
    <div>
      {simulation?.sharp_analysis && (simulation.sharp_analysis.total?.has_edge || simulation.sharp_analysis.spread?.has_edge) ? (
        <div>
          <h3>SHARP SIDE DETECTED</h3>
          
          {simulation.sharp_analysis.total?.has_edge && (
            <div>Total Analysis</div>
          )}
        </div>
      ) : null}
    </div>
  );
};
