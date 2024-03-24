"""Plugin package for BMS types"""

from enum import Enum, auto
from typing import Any
from .basebms import BaseBMS

# import all BMS plugins (class name must match enum)
from .ogt_bms import OGTBms

# define an enum of BMS plugins (class names)
class BmsTypes(Enum):
    OGTBms = auto()

