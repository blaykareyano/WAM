1

   Abaqus 3DEXPERIENCE R2019x                                  Date 10-Feb-2020   Time 10:59:37
   For use by QUEST INTEGRITY USA LLC under license from Dassault Systemes or its subsidiary.

 BISSHOPP AND DRUCKER -- SMALL DISPLACEMENT ANALYSIS            C1               
 SMALL DISPLACEMENT ANALYSIS                                                     
 STEP    1     INCREMENT     1     STEP TIME    0.00    


                        S T E P       1     S T A T I C   A N A L Y S I S


          SMALL DISPLACEMENT ANALYSIS                                                     

          FIXED TIME INCREMENTS
          TIME INCREMENT IS                                    2.220E-16
          TIME PERIOD IS                                       2.220E-16

     LINEAR EQUATION SOLVER TYPE         DIRECT SPARSE

     THIS IS A LINEAR PERTURBATION STEP.
     ALL LOADS ARE DEFINED AS CHANGE IN LOAD TO THE REFERENCE STATE

     EXTRAPOLATION WILL NOT BE USED

     CHARACTERISTIC ELEMENT LENGTH      20.0    

     DETAILS REGARDING ACTUAL SOLUTION WAVEFRONT REQUESTED

     DETAILED OUTPUT OF DIAGNOSTICS TO DATABASE REQUESTED

     PRINT OF INCREMENT NUMBER, TIME, ETC., TO THE MESSAGE FILE EVERY     1  INCREMENTS

     ELEMENT OPERATIONS WILL BE CARRIED OUT IN PARALLEL USING  12 PROCESSORS

     PARALLEL CONTACT TRACKING ENABLED


     COLLECTING MODEL CONSTRAINT INFORMATION FOR OVERCONSTRAINT CHECKS

     COLLECTING STEP CONSTRAINT INFORMATION FOR OVERCONSTRAINT CHECKS
  
     ASYNCHRONOUS OUTPUT DATABASE FRAME FLUSH STARTED
  


  INCREMENT     1 STARTS. ATTEMPT NUMBER  1, TIME INCREMENT  2.220E-16
 
     INITIAL ELEMENT LOAD BALANCE
            PROCESS    1   THREAD     NUMBER OF ELEMENTS
                              1            0
                              2            0
                              3            1
                              4            0
                              5            0
                              6            1
                              7            1
                              8            0
                              9            1
                             10            0
                             11            1
                             12            0

  NUMBER OF EQUATIONS =        18     NUMBER OF RHS =    1
  NUMBER OF FLOATING PT. OPERATIONS =  6.33E+02

  USING THE DIRECT SOLVER WITH  12 PROCESSORS

     CHECK POINT   START OF SOLVER    

     CHECK POINT  END OF SOLVER       

       ELAPSED USER TIME (SEC)      =  0.10000    
       ELAPSED SYSTEM TIME (SEC)    =   0.0000    
       ELAPSED TOTAL CPU TIME (SEC) =  0.10000    
       ELAPSED WALLCLOCK TIME (SEC) =          0
 
     INITIAL ELEMENT LOAD BALANCE
            PROCESS    1   THREAD     NUMBER OF ELEMENTS
                              1            0
                              2            0
                              3            1
                              4            1
                              5            0
                              6            1
                              7            1
                              8            0
                              9            0
                             10            0
                             11            0
                             12            1

 ITERATION SUMMARY FOR THE INCREMENT:   1 TOTAL ITERATIONS, OF WHICH
   0 ARE SEVERE DISCONTINUITY ITERATIONS AND  1 ARE EQUILIBRIUM ITERATIONS.

 TIME INCREMENT COMPLETED  2.220E-16,  FRACTION OF STEP COMPLETED   1.00    
 STEP TIME COMPLETED       2.220E-16,  TOTAL TIME COMPLETED         0.00    


          THE ANALYSIS HAS BEEN COMPLETED



     ANALYSIS SUMMARY:
     TOTAL OF          1  INCREMENTS
                       0  CUTBACKS IN AUTOMATIC INCREMENTATION
                       1  ITERATIONS INCLUDING CONTACT ITERATIONS IF PRESENT
                       1  PASSES THROUGH THE EQUATION SOLVER OF WHICH 
                       1  INVOLVE MATRIX DECOMPOSITION, INCLUDING
                       0  DECOMPOSITION(S) OF THE MASS MATRIX
                       1  REORDERING OF EQUATIONS TO MINIMIZE WAVEFRONT
                       0  ADDITIONAL RESIDUAL EVALUATIONS FOR LINE SEARCHES
                       0  ADDITIONAL OPERATOR EVALUATIONS FOR LINE SEARCHES
                       0  WARNING MESSAGES DURING USER INPUT PROCESSING
                       0  WARNING MESSAGES DURING ANALYSIS
                       0  ANALYSIS WARNINGS ARE NUMERICAL PROBLEM MESSAGES
                       0  ANALYSIS WARNINGS ARE NEGATIVE EIGENVALUE MESSAGES
                       0  ERROR MESSAGES



     JOB TIME SUMMARY
       USER TIME (SEC)      =  0.40000    
       SYSTEM TIME (SEC)    =  0.10000    
       TOTAL CPU TIME (SEC) =  0.50000    
       WALLCLOCK TIME (SEC) =          0
