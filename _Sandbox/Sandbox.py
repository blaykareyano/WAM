## @package Sandbox
# This is for testing of Doxygen
# BOOPS
# =========
# listed boops
# --------
# - boop
#	- sub-boop
#		-# numbered boop
#		-# next numbered boop
#  
# Anything else to say?

## Documentation for a function.
# \todo something really needs to be done here, things are bad
#
# \todo Really tho... do something
#
# Seperate documentation for functions.
def func():
    pass
 
## Documentation for a class.
#
#  seperate documentation for a class.
class PyClass:
   
    ## The constructor.
    def __init__(self):
        self._memVar = 0;
   
    ## Documentation for a method.
    #  @param self The object pointer.
    def PyMethod(self):
        pass
     
    ## A class variable.
    classVar = 0;
 
    ## @var _memVar
    #  a member variable