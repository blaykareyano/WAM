import star.common.Simulation;
import star.common.StarMacro;
import starbom.StarBOM;


public class RunStarCCM extends StarMacro {

	@Override
	public void execute() {

		Simulation sim = getActiveSimulation();
		
		StarBOM.saveEveryNIterations(sim, 250); // save the simulation every 250 iterations
		
	// <CODE_BLOCK_1>	
	// code block 1 used to run any flow simulation until mass balance is achieved
		StarBOM.convergenceTolerance = 0.5;  // the simulation will iterate until the mass balance in the system changes by this much for N iterations; update this value to something sensible (depends on density of fluid, scale of problem, etc.)
		StarBOM.convergenceArrayLength = 50; // we'll run for at least 50 iterations
		StarBOM.runUntilMassFlowConverges(sim);
	// </CODE_BLOCK_1>	
			
	// </CODE_BLOCK_2>		
		//StarBOM.runSim(sim, 2500);  // sample code showing how to run the simulation for 2500 iterations
	// </CODE_BLOCK_2>
		

	// <CODE_BLOCK_3>
	// sample code block below used to show how to run a simulation until 
	// multiple reports have reached steady values 
	
		/*String[] reports = new String[2];
		double[] convergenceCriteria = new double[2];
		
		reports[0] = "massBalance";
		reports[1] = "stdDeviationOutlet";
		
		convergenceCriteria[0] = 0.01;
		convergenceCriteria[1] = 0.01;
		
		StarBOM.convergenceArrayLength = 50;  // we'll run for at least 50 iterations
		
		StarBOM.runUntilConverged(sim, reports, convergenceCriteria); */
	
	// </CODE_BLOCK_3>
		
		StarBOM.saveSimulation(sim);	

	}

}
