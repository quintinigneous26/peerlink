#!/usr/bin/env python3
"""
P2P Engine EventBus 使用示例

演示如何使用统一的 EventBus 系统监听 P2P 引擎事件。
"""
import asyncio
import logging
from p2p_engine.engine import P2PEngine, P2PConfig
from p2p_engine.event import EventTopic, P2PEventType
from p2p_engine.types import PeerInfo, NATInfo, NATType, ISP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def on_connection_event(event):
    """处理连接事件"""
    if event.event_type == P2PEventType.CONNECTION_STATE_CHANGED:
        logger.info(
            f"🔄 状态变化: {event.data['old_state']} -> {event.data['new_state']}"
        )
    elif event.event_type == P2PEventType.PEER_CONNECTED:
        logger.info(f"✅ 对端已连接: {event.peer_id}")
    elif event.event_type == P2PEventType.PEER_DISCONNECTED:
        logger.info(f"❌ 对端已断开: {event.peer_id}")


async def on_error_event(event):
    """处理错误事件"""
    logger.error(
        f"⚠️  错误: {event.data['error_message']} "
        f"(类型: {event.data['error_type']})"
    )
    if 'context' in event.data:
        logger.error(f"   上下文: {event.data['context']}")


async def on_nat_event(event):
    """处理 NAT 检测事件"""
    if event.event_type == P2PEventType.NAT_DETECTED:
        logger.info(
            f"🌐 NAT 检测完成: {event.data.get('nat_type', 'unknown')}"
        )


async def on_all_events(event):
    """监听所有事件（用于调试）"""
    logger.debug(
        f"📡 事件: {event.topic.value}/{event.event_type.value} "
        f"(来源: {event.source})"
    )


async def main():
    """主函数"""
    logger.info("=== P2P Engine EventBus 示例 ===\n")

    # 创建 P2P 引擎
    config = P2PConfig(
        stun_servers=["stun.l.google.com:19302"],
        stun_timeout_ms=3000,
        debug=True,
        log_level="INFO"
    )
    engine = P2PEngine(config=config)

    # 订阅事件
    logger.info("📝 订阅事件...")
    engine.event_bus.subscribe(EventTopic.CONNECTION, on_connection_event)
    engine.event_bus.subscribe(EventTopic.ERROR, on_error_event)
    engine.event_bus.subscribe(EventTopic.NAT, on_nat_event)

    # 可选：订阅所有事件用于调试
    # engine.event_bus.subscribe_all(on_all_events)

    # 启动 EventBus
    await engine.event_bus.start()
    logger.info("✅ EventBus 已启动\n")

    try:
        # 初始化引擎
        logger.info("🚀 初始化 P2P 引擎...")
        await engine.initialize()

        # 模拟状态变化
        logger.info("\n📊 模拟状态变化...")
        await asyncio.sleep(0.5)
        await engine._set_state(engine._state.state)  # 触发事件

        # 模拟错误
        logger.info("\n⚠️  模拟错误...")
        await asyncio.sleep(0.5)
        await engine._emit_error(
            RuntimeError("示例错误"),
            context="demo"
        )

        # 等待事件处理
        await asyncio.sleep(1)

        # 显示 EventBus 指标
        logger.info("\n📈 EventBus 指标:")
        metrics = engine.event_bus.get_metrics()
        for key, value in metrics.items():
            logger.info(f"   {key}: {value}")

    except Exception as e:
        logger.error(f"❌ 错误: {e}")
    finally:
        # 清理
        logger.info("\n🧹 清理资源...")
        await engine.disconnect()
        logger.info("✅ 完成")


async def example_with_callbacks():
    """向后兼容示例：使用旧的回调 API"""
    logger.info("\n=== 向后兼容示例（回调 API） ===\n")

    state_changes = []
    errors = []

    async def on_state_change(old_state, new_state):
        state_changes.append((old_state, new_state))
        logger.info(f"📞 回调: 状态变化 {old_state} -> {new_state}")

    async def on_error(error):
        errors.append(error)
        logger.error(f"📞 回调: 错误 {error}")

    # 使用旧 API
    engine = P2PEngine(
        on_state_change=on_state_change,
        on_error=on_error
    )

    await engine.event_bus.start()

    try:
        await engine.initialize()
        await asyncio.sleep(0.5)

        # 触发事件
        await engine._set_state(engine._state.state)
        await engine._emit_error(RuntimeError("回调测试"))

        await asyncio.sleep(0.5)

        logger.info(f"\n✅ 收到 {len(state_changes)} 个状态变化")
        logger.info(f"✅ 收到 {len(errors)} 个错误")

    finally:
        await engine.disconnect()


async def example_with_filtering():
    """事件过滤示例"""
    logger.info("\n=== 事件过滤示例 ===\n")

    engine = P2PEngine()

    # 只订阅特定类型的连接事件
    async def on_state_change_only(event):
        logger.info(f"🎯 过滤事件: {event.event_type.value}")

    engine.event_bus.subscribe(
        EventTopic.CONNECTION,
        on_state_change_only,
        filter_types={P2PEventType.CONNECTION_STATE_CHANGED}
    )

    await engine.event_bus.start()

    try:
        await engine.initialize()
        await asyncio.sleep(0.5)

        # 这个会被接收
        await engine._set_state(engine._state.state)

        await asyncio.sleep(0.5)

    finally:
        await engine.disconnect()


if __name__ == "__main__":
    # 运行主示例
    asyncio.run(main())

    # 运行向后兼容示例
    asyncio.run(example_with_callbacks())

    # 运行过滤示例
    asyncio.run(example_with_filtering())
