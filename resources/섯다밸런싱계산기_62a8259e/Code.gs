const API_KEY = "api_key = os.environ.get("OPENAI_API_KEY")"; 
const SHEET_ID = "1iP1HfUv5UQKnzOKWcn07N-0wZLby6NahQmFNnkcQavE";

function doGet() {
  return HtmlService.createTemplateFromFile('Index')
      .evaluate()
      .setTitle('섯다 밸런싱 마스터 (V4)')
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getV4Stats() {
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const sheet = ss.getSheetByName("Data");
    const data = sheet.getRange(2, 1, 1, 11).getValues()[0]; // A~K열
    
    const parse = (v) => Number(String(v).replace(/,/g, '')) || 0;

    return {
      serverMoney: parse(data[0]),
      dau: parse(data[1]),
      // 등급별 데이터 구조화
      tiers: {
        whale:  { count: parse(data[2]), burn: parse(data[5]), avgPlay: parse(data[8]) },
        normal: { count: parse(data[3]), burn: parse(data[6]), avgPlay: parse(data[9]) },
        light:  { count: parse(data[4]), burn: parse(data[7]), avgPlay: parse(data[10]) }
      }
    };
  } catch (e) { return { error: e.toString() }; }
}

function askAI_Visual(payload) {
  // AI에게 "HTML로 그림 그려줘"라고 시키는 프롬프트
  const prompt = `
  당신은 카지노 게임 경제 전문가입니다. 아래 시뮬레이션 데이터를 분석하여 HTML 포맷으로 보고서를 작성해주세요.
  
  [시뮬레이션 데이터]
  1. 모드: ${payload.mode === 'supply' ? '재화 지급(Supply)' : '판수 유도(Burn)'}
  2. 대상: ${payload.targetTier.toUpperCase()} 등급 (인원: ${payload.users}명)
  3. 경제 영향:
     - ${payload.impactLabel}: ${payload.totalImpact}
     - 인플레이션/회수율: ${payload.percent}%
  4. 세부 내용:
     - ${payload.detail1}
     - ${payload.detail2}

  [작성 가이드]
  1. **반드시 HTML 태그만 출력하세요.** (Markdown 금지)
  2. 결과는 <div class="ai-report"> 로 감싸주세요.
  3. **막대 그래프 표현:** 중요한 수치(적정성, 위험도 등)는 HTML/CSS로 막대바(<div style="width:XX%; background:...">)를 그려서 시각적으로 보여주세요.
  4. **결론:** "지급액을 10% 줄이세요" 또는 "목표 판수를 90판으로 낮추세요" 처럼 구체적인 숫자로 제안하세요.
  5. 말투는 전문적이고 간결하게.
  `;

  const options = {
    "method": "post",
    "headers": { "Authorization": "Bearer " + API_KEY, "Content-Type": "application/json" },
    "payload": JSON.stringify({
      "model": "gpt-3.5-turbo", // gpt-4o 사용 권장
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.5
    }),
    "muteHttpExceptions": true
  };

  try {
    const res = UrlFetchApp.fetch("https://api.openai.com/v1/chat/completions", options);
    const json = JSON.parse(res.getContentText());
    if (json.error) return "AI 오류: " + json.error.message;
    return json.choices[0].message.content;
  } catch (e) { return "통신 오류"; }
}