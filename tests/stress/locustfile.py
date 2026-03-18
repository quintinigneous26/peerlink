"""
Locust压力测试脚本
使用方法: locust -f tests/stress/locustfile.py
"""
import asyncio
import json
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


class P2PPlatformUser(HttpUser):
    """P2P平台用户行为模拟"""

    # 等待时间: 1-3秒之间
    wait_time = between(1, 3)

    def on_start(self):
        """用户启动时的初始化"""
        # 注册设备
        self.device_id = f"device_{int(time.time() * 1000)}"
        self.register_device()

    @task(3)
    def stun_request(self):
        """STUN请求 (权重3)"""
        with self.client.get(
            "/stun/binding",
            name="STUN Binding Request",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"STUN request failed: {response.status_code}")

    @task(5)
    def did_resolve(self):
        """DID解析 (权重5)"""
        did = f"did:p2p:{self.device_id}"
        with self.client.get(
            f"/did/resolve/{did}",
            name="DID Resolve",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"DID resolve failed: {response.status_code}")

    @task(2)
    def signaling_connect(self):
        """信令连接 (权重2)"""
        payload = {
            "device_id": self.device_id,
            "device_type": "test_client",
        }
        with self.client.post(
            "/signaling/connect",
            json=payload,
            name="Signaling Connect",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Signaling connect failed: {response.status_code}")

    @task(4)
    def register_device(self):
        """设备注册 (权重4)"""
        payload = {
            "device_id": self.device_id,
            "device_type": "mobile",
            "capabilities": ["audio", "video"],
        }
        with self.client.post(
            "/did/register",
            json=payload,
            name="DID Register",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                data = response.json()
                if "did" in data:
                    self.did = data["did"]
                    response.success()
                else:
                    response.failure("No DID in response")
            else:
                response.failure(f"Registration failed: {response.status_code}")

    @task(3)
    def create_offer(self):
        """创建连接Offer (权重3)"""
        if not hasattr(self, "did"):
            return

        payload = {
            "device_id": self.device_id,
            "peer_id": f"peer_{int(time.time())}",
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n...",
        }
        with self.client.post(
            "/signaling/offer",
            json=payload,
            name="Create Offer",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Offer creation failed: {response.status_code}")

    @task(2)
    def allocate_relay(self):
        """分配Relay (权重2)"""
        payload = {
            "device_id": self.device_id,
            "peer_id": f"peer_{int(time.time())}",
            "lifetime": 3600,
        }
        with self.client.post(
            "/relay/allocate",
            json=payload,
            name="Relay Allocate",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Relay allocation failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """健康检查 (权重1)"""
        with self.client.get(
            "/health",
            name="Health Check",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class HighLoadUser(P2PPlatformUser):
    """高负载用户 - 更短的等待时间"""

    wait_time = between(0.1, 0.5)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的统计"""
    if isinstance(environment.runner, MasterRunner):
        return

    stats = environment.stats
    print("\n" + "=" * 60)
    print("测试完成统计")
    print("=" * 60)
    print(f"总请求数: {stats.total.num_requests}")
    print(f"失败请求数: {stats.total.num_failures}")
    print(f"平均响应时间: {stats.total.avg_response_time:.2f}ms")
    print(f"中位数响应时间: {stats.total.median_response_time:.2f}ms")
    print(f"95%响应时间: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99%响应时间: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"请求数/秒: {stats.total.total_rps:.2f}")
    print("=" * 60 + "\n")


# 性能阈值监听器
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """请求监听 - 检测慢请求"""
    if exception:
        print(f"请求失败: {name} - {exception}")
    elif response_time > 1000:  # 超过1秒的请求
        print(f"慢请求警告: {name} - {response_time:.2f}ms")
