// 简单的前端测试脚本，用于从浏览器或 Node 环境测试 /api/chat/stream 的流式输出。
// 使用方式一（浏览器控制台）：
//   1. 启动后端：uvicorn src.api.server:app --reload
//   2. 在任意页面打开浏览器控制台，粘贴本文件内容
//   3. 调用：startStream("帮我用 MA 策略回测最近 30 天 BTCUSDT 1h")
//
// 使用方式二（简单 HTML）：
//   1. 在本地新建 test.html，引入本脚本
//   2. 在页面按钮点击时调用 startStream。

const API_BASE = "http://127.0.0.1:8000";

async function startStream(message, sessionId = "demo-session", options = {}) {
  const { onToken, onDone, onError } = options || {};

  const url = `${API_BASE}/api/chat/stream`;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!resp.ok || !resp.body) {
    console.error("请求失败", resp.status, resp.statusText);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let accumulatedText = "";

  console.log("开始流式接收...");

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      console.log("流结束");
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);

      if (!raw.startsWith("data:")) continue;
      const jsonStr = raw.slice(5).trim();
      if (!jsonStr) continue;

      let evt;
      try {
        evt = JSON.parse(jsonStr);
      } catch (e) {
        console.warn("解析流事件 JSON 失败", e, jsonStr);
        continue;
      }

      if (evt.event === "token") {
        const text = evt.text || "";
        accumulatedText += text;
        if (typeof onToken === "function") {
          onToken(text, accumulatedText);
        } else {
          // 默认行为：直接在控制台输出 token
          console.log(text);
        }
      } else if (evt.event === "done") {
        if (typeof onDone === "function") {
          onDone(evt.result, accumulatedText);
        } else {
          console.log("\n==== 最终结果 result ====");
          console.log(evt.result);
          console.log("\n==== 汇总回答 output 文本 ====");
          console.log(accumulatedText || (evt.result && evt.result.output));
        }
      } else if (evt.event === "error") {
        if (typeof onError === "function") {
          onError(evt);
        } else {
          console.error("流式错误:", evt.message);
        }
      } else {
        console.log("收到其他事件", evt);
      }

    }
  }
}

// 为了方便在浏览器控制台中调用
if (typeof window !== "undefined") {
  window.startStream = startStream;
}
