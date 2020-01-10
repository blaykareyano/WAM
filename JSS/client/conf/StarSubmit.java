// STAR-CCM+ macro: StarSubmit.java
package macro;

import java.util.*;

import star.common.*;
import star.base.neo.*;

public class StarSubmit extends StarMacro {

  public void execute() {
    execute0();
  }

  private void execute0() {

    Simulation sim =
      getActiveSimulation();

    sim.getSimulationIterator().step(2500);

    // save results:
    sim.saveState(resolvePath(sim.getSessionPath()));

  }
}