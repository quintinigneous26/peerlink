"""配置模块"""
from .defaults import DEFAULT_CONFIG, Config
from .isp_profiles import ISPProfile, ISP_PROFILES, get_isp_profile, is_cross_border, is_cross_isp
from .loader import ConfigLoader

__all__ = [
    "DEFAULT_CONFIG",
    "Config",
    "ISPProfile",
    "ISP_PROFILES",
    "get_isp_profile",
    "is_cross_border",
    "is_cross_isp",
    "ConfigLoader",
]
