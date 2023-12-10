from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

class OperationModeEnum(str, Enum):
    client = "client"
    AP = "AP"

class RadioEnum(str, Enum):
    radio0 = "5G"
    radio1 = "2.4G"

class ConfigureClientData(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    radio: RadioEnum
    connect_to_target_ap: bool
    ssid: str
    password: Optional[str] = None
    
class ConfigureAccessPointData(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    radio: RadioEnum
    ssid: str
    tx_power: Optional[int] = 20
    
# password already be preconfigure in case it is ap_mode or client_mode that not connect to target ap
# else: need the password