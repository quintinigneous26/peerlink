/*
 @licstart  The following is the entire license notice for the JavaScript code in this file.

 The MIT License (MIT)

 Copyright (C) 1997-2020 by Dimitri van Heesch

 Permission is hereby granted, free of charge, to any person obtaining a copy of this software
 and associated documentation files (the "Software"), to deal in the Software without restriction,
 including without limitation the rights to use, copy, modify, merge, publish, distribute,
 sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in all copies or
 substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
 BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

 @licend  The above is the entire license notice for the JavaScript code in this file
*/
var NAVTREE =
[
  [ "P2P Platform", "index.html", [
    [ "P2P Platform 文档", "index.html", "index" ],
    [ "P2P 平台传输层与复用层 - 深度优化报告", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html", [
      [ "执行摘要", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md1", null ],
      [ "1. 性能瓶颈分析", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md3", [
        [ "1.1 识别的关键瓶颈", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md4", null ],
        [ "1.2 目标性能指标", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md5", null ]
      ] ],
      [ "2. 优化实施", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md7", [
        [ "2.1 传输层优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md8", [
          [ "TCP Fast Open 实现", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md9", null ],
          [ "QUIC 0-RTT 实现", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md10", null ]
        ] ],
        [ "2.2 流复用优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md11", [
          [ "Mplex V2 实现", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md12", null ],
          [ "Yamux 优化实现", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md13", null ]
        ] ],
        [ "2.3 DHT 优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md14", [
          [ "查询优化器", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md15", null ]
        ] ],
        [ "2.4 NAT 穿透优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md16", null ]
      ] ],
      [ "3. 性能基准测试", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md18", [
        [ "3.1 基准测试框架", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md19", null ],
        [ "3.2 预期测试结果", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md20", null ]
      ] ],
      [ "4. 文件清单", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md22", [
        [ "新增文件", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md23", null ],
        [ "修改文件", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md24", null ]
      ] ],
      [ "5. 使用示例", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md26", [
        [ "5.1 使用优化的 TCP 传输", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md27", null ],
        [ "5.2 使用优化的 Yamux", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md28", null ],
        [ "5.3 使用 DHT 查询优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md29", null ]
      ] ],
      [ "6. 后续工作", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md31", [
        [ "6.1 集成测试", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md32", null ],
        [ "6.2 进一步优化", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md33", null ],
        [ "6.3 监控和度量", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md34", null ]
      ] ],
      [ "7. 结论", "md_p2p__engine_2transport_2_o_p_t_i_m_i_z_a_t_i_o_n___r_e_p_o_r_t.html#autotoc_md36", null ]
    ] ],
    [ "P2P 传输层与复用层性能分析报告", "md_p2p__engine_2transport_2performance__analysis.html", [
      [ "执行摘要", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md39", null ],
      [ "1. 性能瓶颈分析", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md41", [
        [ "1.1 传输层 (transport/)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md42", [
          [ "现状", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md43", null ],
          [ "瓶颈点", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md44", null ]
        ] ],
        [ "1.2 流复用 (muxer/)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md45", [
          [ "现状", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md46", null ],
          [ "瓶颈点", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md47", null ]
        ] ],
        [ "1.3 DHT (dht/)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md48", [
          [ "瓶颈点", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md49", null ]
        ] ],
        [ "1.4 NAT 穿透 (puncher/)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md50", [
          [ "瓶颈点", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md51", null ]
        ] ]
      ] ],
      [ "2. 优化方案", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md53", [
        [ "2.1 TCP 传输优化", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md54", [
          [ "TCP Fast Open (TFO)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md55", null ]
        ] ],
        [ "2.2 Yamux 优化", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md56", [
          [ "流 ID 预分配池", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md57", null ]
        ] ],
        [ "2.3 Mplex 帧解析优化", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md58", [
          [ "智能帧解析", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md59", null ]
        ] ],
        [ "2.4 DHT 查询优化", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md60", [
          [ "自适应并发度", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md61", null ]
        ] ]
      ] ],
      [ "3. 优化实施计划", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md63", [
        [ "Phase 1: 快速胜利 (Quick Wins)", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md64", null ],
        [ "Phase 2: 架构优化", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md65", null ],
        [ "Phase 3: 高级特性", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md66", null ]
      ] ],
      [ "4. 性能目标", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md68", null ],
      [ "5. 代码改进", "md_p2p__engine_2transport_2performance__analysis.html#autotoc_md70", null ]
    ] ],
    [ "Changelog", "md_client__sdk_2_c_h_a_n_g_e_l_o_g.html", [
      [ "<a href=\"https://github.com/p2p-platform/python-sdk/compare/v0.1.0...HEAD\">Unreleased</a>", "md_client__sdk_2_c_h_a_n_g_e_l_o_g.html#autotoc_md72", null ],
      [ "<a href=\"https://github.com/p2p-platform/python-sdk/releases/tag/v0.1.0\">0.1.0</a> - 2026-03-15", "md_client__sdk_2_c_h_a_n_g_e_l_o_g.html#autotoc_md73", [
        [ "Added", "md_client__sdk_2_c_h_a_n_g_e_l_o_g.html#autotoc_md74", null ],
        [ "Features", "md_client__sdk_2_c_h_a_n_g_e_l_o_g.html#autotoc_md75", null ]
      ] ]
    ] ],
    [ "P2P SDK API 参考文档", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html", [
      [ "核心类", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md77", [
        [ "P2PClient", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md78", [
          [ "构造函数", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md79", null ],
          [ "方法", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md80", [
            [ "async initialize()", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md81", null ],
            [ "async detect_nat() -&gt; NATType", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md82", null ],
            [ "async connect(did: str) -&gt; bool", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md83", null ],
            [ "async send_data(channel: int, data: bytes) -&gt; None", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md84", null ],
            [ "async recv_data(channel: int, timeout: float = None) -&gt; bytes", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md85", null ],
            [ "create_channel(channel_type: ChannelType, reliable: bool = True, priority: int = 0) -&gt; int", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md86", null ],
            [ "close_channel(channel_id: int) -&gt; None", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md87", null ],
            [ "async close() -&gt; None", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md88", null ],
            [ "async measure_latency() -&gt; float", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md89", null ],
            [ "get_statistics() -&gt; dict", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md90", null ]
          ] ],
          [ "属性", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md91", [
            [ "nat_type: NATType", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md92", null ],
            [ "local_address: tuple[str, int]", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md93", null ],
            [ "public_address: tuple[str, int]", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md94", null ],
            [ "is_connected: bool", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md95", null ],
            [ "is_signaling_connected: bool", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md96", null ],
            [ "peer_did: str | None", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md97", null ]
          ] ],
          [ "事件处理器", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md98", [
            [ "@client.on_connected", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md99", null ],
            [ "@client.on_disconnected", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md100", null ],
            [ "@client.on_data", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md101", null ],
            [ "@client.on_error", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md102", null ],
            [ "@client.on_channel_opened", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md103", null ],
            [ "@client.on_channel_closed", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md104", null ]
          ] ]
        ] ]
      ] ],
      [ "枚举类型", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md105", [
        [ "ChannelType", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md106", null ],
        [ "NATType", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md107", null ]
      ] ],
      [ "异常类", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md108", [
        [ "P2PError", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md109", null ],
        [ "ConnectionError", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md110", null ],
        [ "NATDetectionError", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md111", null ],
        [ "RelayError", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md112", null ],
        [ "TimeoutError", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md113", null ]
      ] ],
      [ "工具函数", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md114", [
        [ "async detect_nat_type(stun_server: str, stun_port: int) -&gt; NATType", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md115", null ]
      ] ],
      [ "协议格式", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md116", [
        [ "消息格式", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md117", null ],
        [ "消息类型", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md118", [
          [ "handshake", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md119", null ],
          [ "keepalive", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md120", null ],
          [ "channel_data", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md121", null ],
          [ "channel_open", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md122", null ],
          [ "channel_close", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md123", null ],
          [ "disconnect", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md124", null ],
          [ "error", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md125", null ]
        ] ]
      ] ],
      [ "配置示例", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md126", [
        [ "最小配置", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md127", null ],
        [ "生产环境配置", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md128", null ],
        [ "高性能配置", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md129", null ],
        [ "低延迟配置", "md_client__sdk_2docs_2_a_p_i___r_e_f_e_r_e_n_c_e.html#autotoc_md130", null ]
      ] ]
    ] ],
    [ "P2P SDK 最佳实践指南", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html", [
      [ "1. 资源管理", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md132", [
        [ "1.1 始终清理资源", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md133", null ],
        [ "1.2 使用上下文管理器（如果支持）", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md134", null ]
      ] ],
      [ "2. 错误处理", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md135", [
        [ "2.1 捕获特定异常", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md136", null ],
        [ "2.2 实现重试逻辑", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md137", null ]
      ] ],
      [ "3. 性能优化", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md138", [
        [ "3.1 通道优先级", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md139", null ],
        [ "3.2 批量发送", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md140", null ],
        [ "3.3 缓冲区调优", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md141", null ],
        [ "3.4 并发处理", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md142", null ]
      ] ],
      [ "4. 网络适��", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md143", [
        [ "4.1 NAT 类型处理", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md144", null ],
        [ "4.2 网络状态监控", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md145", null ],
        [ "4.3 超时配置", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md146", null ]
      ] ],
      [ "5. 安全实践", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md147", [
        [ "5.1 设备 ID 管理", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md148", null ],
        [ "5.2 数据加密", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md149", null ],
        [ "5.3 访问控制", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md150", null ]
      ] ],
      [ "6. 日志和调试", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md151", [
        [ "6.1 启用日志", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md152", null ],
        [ "6.2 性能监控", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md153", null ],
        [ "6.3 错误追踪", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md154", null ]
      ] ],
      [ "7. 测试", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md155", [
        [ "7.1 单元测试", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md156", null ],
        [ "7.2 集成测试", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md157", null ],
        [ "7.3 压力测试", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md158", null ]
      ] ],
      [ "8. 部署", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md159", [
        [ "8.1 生产环境配置", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md160", null ],
        [ "8.2 容器化", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md161", null ],
        [ "8.3 健康检查", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md162", null ]
      ] ],
      [ "9. 常见问题", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md163", [
        [ "9.1 连接失败", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md164", null ],
        [ "9.2 性能问题", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md165", null ],
        [ "9.3 内存泄漏", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md166", null ]
      ] ],
      [ "10. 总结", "md_client__sdk_2docs_2_b_e_s_t___p_r_a_c_t_i_c_e_s.html#autotoc_md167", null ]
    ] ],
    [ "P2P SDK 快速开始指南", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html", [
      [ "安装", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md170", [
        [ "从 PyPI 安装", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md171", null ],
        [ "从 Conda 安装", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md172", null ],
        [ "从源码安装", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md173", null ]
      ] ],
      [ "基础使用", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md174", [
        [ "1. 创建客户端", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md175", null ],
        [ "2. 连接到对等设备", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md176", null ],
        [ "3. 发送和接收数据", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md177", null ]
      ] ],
      [ "高级功能", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md178", [
        [ "多通道通信", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md179", null ],
        [ "事件处理", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md180", null ],
        [ "自定义配置", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md181", null ]
      ] ],
      [ "NAT 类型检测", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md185", null ],
      [ "错误处理", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md187", null ],
      [ "最佳实践", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md190", [
        [ "1. 资源管理", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md192", null ],
        [ "2. 超时设置", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md193", null ],
        [ "3. 错误重试", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md195", null ],
        [ "4. 日志记录", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md196", null ],
        [ "5. 网络状态监控", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md206", null ]
      ] ],
      [ "性能优化", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md209", [
        [ "1. 通道优先级", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md211", null ],
        [ "2. 批量发送", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md214", null ],
        [ "3. 缓冲区大小", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md217", null ]
      ] ],
      [ "故障排查", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md219", [
        [ "连接失败", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md220", null ],
        [ "性能问题", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md222", null ]
      ] ],
      [ "更多示例", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md225", null ],
      [ "支持", "md_client__sdk_2docs_2_q_u_i_c_k_s_t_a_r_t.html#autotoc_md227", null ]
    ] ],
    [ "P2P SDK 发布指南", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html", [
      [ "构建和发布流程", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md182", [
        [ "1. 准备发布", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md183", [
          [ "1.1 更新版本号", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md184", null ],
          [ "1.2 更新 CHANGELOG", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md186", null ],
          [ "1.3 运行测试", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md188", null ]
        ] ],
        [ "2. 构建包", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md189", [
          [ "2.1 构建 Python Wheel", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md191", null ],
          [ "2.2 构建 Conda 包", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md194", null ]
        ] ],
        [ "3. 本地测试", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md197", [
          [ "3.1 测试 Wheel 包", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md198", null ],
          [ "3.2 测试 Conda 包", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md199", null ]
        ] ],
        [ "4. 发布到 Test PyPI", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md200", [
          [ "4.1 配置凭证", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md201", null ],
          [ "4.2 上传到 Test PyPI", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md202", null ],
          [ "4.3 从 Test PyPI 安装测试", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md203", null ]
        ] ],
        [ "5. 发布到生产 PyPI", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md204", [
          [ "5.1 最终检查", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md205", null ],
          [ "5.2 创建 Git 标签", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md207", null ],
          [ "5.3 上传到 PyPI", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md208", null ],
          [ "5.4 验证发布", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md210", null ]
        ] ],
        [ "6. 发布到 Conda", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md212", [
          [ "6.1 上传到 Anaconda Cloud", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md213", null ],
          [ "6.2 验证", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md215", null ]
        ] ],
        [ "7. 发布 GitHub Release", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md216", [
          [ "7.1 创建 Release", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md218", null ],
          [ "7.2 更新文档", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md221", null ]
        ] ]
      ] ],
      [ "发布检查清单", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md223", [
        [ "发布前", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md224", null ],
        [ "构建", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md226", null ],
        [ "测试", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md228", null ],
        [ "发布", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md229", null ],
        [ "发布后", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md230", null ]
      ] ],
      [ "回滚流程", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md231", [
        [ "1. PyPI 回滚", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md232", null ],
        [ "2. 标记为 Yanked", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md233", null ],
        [ "3. Git 回滚", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md234", null ]
      ] ],
      [ "自动化发布", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md235", [
        [ "GitHub Actions 工作流", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md236", null ]
      ] ],
      [ "版本策略", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md237", null ],
      [ "支持的 Python 版本", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md238", null ],
      [ "许可证", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md239", null ],
      [ "联系方式", "md_client__sdk_2docs_2_r_e_l_e_a_s_e___g_u_i_d_e.html#autotoc_md240", null ]
    ] ],
    [ "P2P Platform", "md__r_e_a_d_m_e.html", [
      [ "📖 项目简介", "md__r_e_a_d_m_e.html#autotoc_md267", [
        [ "核心优势", "md__r_e_a_d_m_e.html#autotoc_md268", null ]
      ] ],
      [ "✨ 主要特性", "md__r_e_a_d_m_e.html#autotoc_md270", [
        [ "核心服务", "md__r_e_a_d_m_e.html#autotoc_md271", null ],
        [ "libp2p 协议栈", "md__r_e_a_d_m_e.html#autotoc_md272", [
          [ "安全传输", "md__r_e_a_d_m_e.html#autotoc_md273", null ],
          [ "流复用", "md__r_e_a_d_m_e.html#autotoc_md274", null ],
          [ "核心协议", "md__r_e_a_d_m_e.html#autotoc_md275", null ],
          [ "高级功能", "md__r_e_a_d_m_e.html#autotoc_md276", null ],
          [ "传输层", "md__r_e_a_d_m_e.html#autotoc_md277", null ]
        ] ],
        [ "网络优化", "md__r_e_a_d_m_e.html#autotoc_md278", null ]
      ] ],
      [ "🚀 快速开始", "md__r_e_a_d_m_e.html#autotoc_md280", [
        [ "前置要求", "md__r_e_a_d_m_e.html#autotoc_md281", null ],
        [ "使用 Docker Compose (推荐)", "md__r_e_a_d_m_e.html#autotoc_md282", null ],
        [ "使用客户端 SDK", "md__r_e_a_d_m_e.html#autotoc_md283", null ]
      ] ],
      [ "📦 安装方式", "md__r_e_a_d_m_e.html#autotoc_md285", [
        [ "方式 1: Docker (推荐)", "md__r_e_a_d_m_e.html#autotoc_md286", null ],
        [ "方式 2: RPM 包 (CentOS/RHEL/Fedora)", "md__r_e_a_d_m_e.html#autotoc_md287", null ],
        [ "方式 3: DEB 包 (Ubuntu/Debian)", "md__r_e_a_d_m_e.html#autotoc_md288", null ],
        [ "方式 4: pip 安装 (仅客户端 SDK)", "md__r_e_a_d_m_e.html#autotoc_md289", null ],
        [ "方式 5: 源码安装", "md__r_e_a_d_m_e.html#autotoc_md290", null ]
      ] ],
      [ "📚 文档", "md__r_e_a_d_m_e.html#autotoc_md292", [
        [ "核心文档", "md__r_e_a_d_m_e.html#autotoc_md293", null ],
        [ "技术文档", "md__r_e_a_d_m_e.html#autotoc_md294", null ],
        [ "发布说明", "md__r_e_a_d_m_e.html#autotoc_md295", null ]
      ] ],
      [ "🧪 测试", "md__r_e_a_d_m_e.html#autotoc_md297", null ],
      [ "🛠️ 配置", "md__r_e_a_d_m_e.html#autotoc_md299", [
        [ "环境变量", "md__r_e_a_d_m_e.html#autotoc_md300", null ],
        [ "配置文件", "md__r_e_a_d_m_e.html#autotoc_md301", null ]
      ] ],
      [ "📊 性能指标", "md__r_e_a_d_m_e.html#autotoc_md303", null ],
      [ "🤝 贡献指南", "md__r_e_a_d_m_e.html#autotoc_md305", [
        [ "如何贡献", "md__r_e_a_d_m_e.html#autotoc_md306", null ],
        [ "提交规范", "md__r_e_a_d_m_e.html#autotoc_md307", null ],
        [ "代码规范", "md__r_e_a_d_m_e.html#autotoc_md308", null ]
      ] ],
      [ "📄 许可证", "md__r_e_a_d_m_e.html#autotoc_md310", null ],
      [ "🙏 致谢", "md__r_e_a_d_m_e.html#autotoc_md312", null ],
      [ "📞 联系我们", "md__r_e_a_d_m_e.html#autotoc_md314", null ]
    ] ],
    [ "命名空间", "namespaces.html", [
      [ "命名空间列表", "namespaces.html", "namespaces_dup" ],
      [ "命名空间成员", "namespacemembers.html", [
        [ "全部", "namespacemembers.html", "namespacemembers_dup" ],
        [ "函数", "namespacemembers_func.html", null ],
        [ "变量", "namespacemembers_vars.html", "namespacemembers_vars" ]
      ] ]
    ] ],
    [ "类", "annotated.html", [
      [ "类列表", "annotated.html", "annotated_dup" ],
      [ "类索引", "classes.html", null ],
      [ "类继承关系", "hierarchy.html", "hierarchy" ],
      [ "类成员", "functions.html", [
        [ "全部", "functions.html", "functions_dup" ],
        [ "函数", "functions_func.html", "functions_func" ],
        [ "变量", "functions_vars.html", "functions_vars" ]
      ] ]
    ] ],
    [ "文件", "files.html", [
      [ "文件列表", "files.html", "files_dup" ],
      [ "文件成员", "globals.html", [
        [ "全部", "globals.html", null ],
        [ "变量", "globals_vars.html", null ]
      ] ]
    ] ]
  ] ]
];

var NAVTREEINDEX =
[
"allocation_8py.html",
"classp2p__engine_1_1detection_1_1autonat_1_1_auto_n_a_t_client.html#a7dd7134722e94af5c3bfb810f0a7ac28",
"classp2p__engine_1_1dht_1_1kademlia_1_1_kademlia_d_h_t.html#a233dfabaf67490b0dd33cab024df9008",
"classp2p__engine_1_1dht_1_1query__optimizer_1_1_optimized_query_manager.html",
"classp2p__engine_1_1engine_1_1_p2_p_state.html#a44e835b8d511d2ecafcdf7169f4ceec0",
"classp2p__engine_1_1keeper_1_1heartbeat_1_1_heartbeat_keeper.html#a935bf43c166068b9bd6e5091b1481e3f",
"classp2p__engine_1_1muxer_1_1mplex__adapter_1_1_connection_writer.html#aad65814f761029ddcb19a579ddf1b1e1",
"classp2p__engine_1_1muxer_1_1mplex__v2_1_1_mplex_stream_closed.html",
"classp2p__engine_1_1muxer_1_1yamux_1_1_yamux_stream.html#adc2e085b0c40e1924631dc6c10522c94",
"classp2p__engine_1_1protocol_1_1identify_1_1_identify_message.html#a4fafd317a5588a370731b87c053ee754",
"classp2p__engine_1_1protocol_1_1noise_1_1_noise_handshake.html#a459ebe5b24a7a00e372c2f56e5ca86e2",
"classp2p__engine_1_1protocol_1_1pubsub_1_1_control_prune.html#a586713f60f846ea0bad631d4c12a0dbf",
"classp2p__engine_1_1protocol_1_1pubsub_1_1_message_cache.html#a24368ed7f0d0a323117101afd953eb01",
"classp2p__engine_1_1puncher_1_1port__predictor_1_1_port_predictor.html#a042853f688a1157395678fc66d307e3e",
"classp2p__engine_1_1transport_1_1quic_1_1_q_u_i_c_connection.html#a814e69add95d4d56bdb6f91aea91b26e",
"classp2p__engine_1_1transport_1_1quic__0rtt_1_1_session_ticket_store.html#ab233486610a1085d46abd5626de6a82f",
"classp2p__engine_1_1transport_1_1upgrader_1_1_transport_upgrader.html#a1c464f41c5ff893d3291a6374c213e43",
"classp2p__engine_1_1transport_1_1webtransport_1_1_web_transport_connection.html#a122cb7bddeb5efaf622d1889453559cc",
"classp2p__engine_1_1types_1_1_i_s_p.html#a823bf6c7dbe601545cfee3970190aece",
"classp2p__sdk_1_1client_1_1_p2_p_client.html#aed6965e37ab30e2a4bacea5adeb0c36b",
"classp2p__sdk_1_1signaling_1_1_web_socket_signaling_client.html",
"classsrc_1_1bandwidth_1_1_throughput_monitor.html#ae369e64cad9d047bf2ca60bc646c8deb",
"classsrc_1_1did__service_1_1service_1_1_verify_d_i_d_request.html#a4176529d4b4ca72e62fc6f062503349b",
"classsrc_1_1relay_1_1_relay_server.html#a9f022fd5f5ce3729dbf930487a8b934c",
"classsrc_1_1signaling__server_1_1config_1_1_config.html#a0a6bb4d4fe2211e77a8fbe02042f05f0",
"classsrc_1_1signaling__server_1_1models_1_1_message_type.html#af95bc1841d1069f6bda2261b0ad4b158",
"md__r_e_a_d_m_e.html#autotoc_md295",
"multi__channel_8py_source.html",
"namespacep2p__engine_1_1protocol.html#a7b34c3526904e31aa45735385d356a63",
"namespacesrc_1_1allocation.html#aa1f2407069c30f1807d43b9e26b5d825",
"stun__client_8py.html"
];

var SYNCONMSG = '点击 关闭 面板同步';
var SYNCOFFMSG = '点击 开启 面板同步';
var LISTOFALLMEMBERS = '所有成员列表';