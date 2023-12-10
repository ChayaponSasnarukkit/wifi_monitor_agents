from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

class OperationModeEnum(str, Enum):
    client = "client"
    AP = "AP"

class RadioEnum(str, Enum):
    radio0 = "5G"
    radio1 = "2.4G"

class ConfigureData(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    
    mode: OperationModeEnum
    radio: RadioEnum
    connect_to_target_ap: bool
    ssid: str
    password: Optional[str] = "xxreJMeExxzT8fI"
    tx_power: Optional[int] = None