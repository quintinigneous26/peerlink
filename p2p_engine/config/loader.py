"""
配置加载器

支持：
  1. 本地配置文件
  2. 远程配置中心
  3. 热更新
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable

from .defaults import Config, DEFAULT_CONFIG
from .isp_profiles import ISPProfile, get_isp_profile
from ..types import ISP
from typing import Any

logger = logging.getLogger("p2p_engine.config")


def deep_merge(base: dict, override: dict) -> dict:
    """
    深度合并两个字典。

    规则:
    1. override 中的键值覆盖 base 中的同名键
    2. 如果两个值都是字典，递归合并
    3. 其他情况直接覆盖

    Args:
        base: 基础字典
        override: 覆盖字典

    Returns:
        合并后的新字典（不修改原字典）
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


class ConfigLoader:
    """配置加载器"""
    
    def __init__(
        self,
        local_config_path: Optional[str] = None,
        remote_config_url: Optional[str] = None,
    ):
        self.local_config_path = local_config_path
        self.remote_config_url = remote_config_url
        
        self._config = DEFAULT_CONFIG
        self._isp_profile: Optional[ISPProfile] = None
        self._remote_task: Optional[asyncio.Task] = None
        
        # 热更新回调
        self._on_update: Optional[Callable[[Config], Awaitable[None]]] = None
    
    @property
    def config(self) -> Config:
        """获取当前配置"""
        return self._config
    
    @property
    def isp_profile(self) -> ISPProfile:
        """获取当前运营商配置"""
        return self._isp_profile or get_isp_profile(ISP.UNKNOWN)
    
    async def load(self) -> Config:
        """
        加载配置（启动时调用）
        
        1. 立即加载本地配置
        2. 后台异步拉取远程配置
        """
        # 1. 加载本地配置（同步，不阻塞）
        await self._load_local()
        
        # 2. 后台拉取远程配置（不阻塞）
        if self.remote_config_url:
            self._remote_task = asyncio.create_task(self._load_remote())
        
        return self._config
    
    async def _load_local(self) -> None:
        """加载本地配置"""
        if not self.local_config_path:
            logger.debug("未指定本地配置文件，使用默认配置")
            return
        
        path = Path(self.local_config_path)
        if not path.exists():
            logger.warning(f"本地配置文件不存在: {path}")
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._merge_config(data)
            logger.info(f"已加载本地配置: {path}")
            
        except Exception as e:
            logger.error(f"加载本地配置失败: {e}")
    
    async def _load_remote(self) -> None:
        """加载远程配置（后台）"""
        if not self.remote_config_url:
            return
        
        try:
            # TODO: 实现远程配置拉取
            # 这里可以用 HTTP 请求获取配置
            logger.debug(f"开始拉取远程配置: {self.remote_config_url}")
            
            # 模拟远程请求
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(self.remote_config_url) as resp:
            #         data = await resp.json()
            #         self._merge_config(data)
            #         logger.info("已加载远程配置")
            
            # 触发更新回调
            if self._on_update:
                await self._on_update(self._config)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"加载远程配置失败: {e}")
    
    def _merge_config(self, data: dict) -> None:
        """深度合并配置到当前配置

        支持嵌套配置合并，保留未指定的默认值

        Args:
            data: 要合并的配置字典
        """
        # 使用 Config.merge 方法进行深度合并
        self._config.merge(data)
        logger.debug(f"配置已合并: {list(data.keys())}")
    
    def set_isp(self, isp: ISP) -> None:
        """设置当前运营商（探测完成后调用）"""
        self._isp_profile = get_isp_profile(isp)
        logger.info(f"已设置运营商: {self._isp_profile.name}")
    
    def on_update(self, callback: Callable[[Config], Awaitable[None]]) -> None:
        """注册配置更新回调"""
        self._on_update = callback
    
    async def close(self) -> None:
        """关闭加载器"""
        if self._remote_task:
            self._remote_task.cancel()
            try:
                await self._remote_task
            except asyncio.CancelledError:
                pass
