// --- 1. 설정 ---
const SPREADSHEET_ID = '1apJSHUQ_fZzWqT_KlpRvXoeSVhx-aF2ansqilTHKqlY'; 
const SHEET_NAME = '이슈 요약'; 
const TARGET_SPACE_KEYWORDS = ['뉴맞고', '섯다']; // (원하는 키워드로 수정)
const HOURS_AGO = 24; 

// (v2.2 - 5가지 카테고리로 수정됨)
const SYSTEM_PROMPT = `
당신은 Google Chat 메시지를 분석하여 '일일 업무 요약'을 생성하는 전문 PM 어시스턴트입니다.
제공되는 채팅 로그는 여러 스페이스의 내용을 포함하고 있습니다.

당신의 임무는 각 스페이스별로 채팅 내용을 다음 5가지 카테고리로 엄격하게 분류하여 요약하는 것입니다:

1.  **[‼️ 이슈/QA/장애]**:
    * (장애 리포트, 버그, 사용자 불만, 긴급 수정 요청, QA 요청)
    * (예: "Live 환경 문제", "Jira 이슈 등록", "hide 시나리오", "로그인 오류")

2.  **[❓ 문의/질의]**: (새로 추가된 카테고리)
    * (단순 문의, 정책 질의, 기능 확인 요청)
    * (예: "GRC 호스트 문의", "이거 정책이 어떻게 되죠?", "기능 스펙 확인 요청")

3.  **[✍️ 기획/수정/정책]**:
    * (기획서 변경, 디자인 수정, 신규 기능 제안, 정책 변경)
    * (예: "기획서 순서 정렬", "상세 통계 팝업 개선", "신규 정책 공유")

4.  **[📢 공지/로그/일정]**:
    * (단순 공지, 일정 공유, 담당자 지정, 데이터 공유)
    * (예: "모니터링 종료", "Live 데이터 로그 공유", "PMS 777 날리겠습니다")

5.  **[💬 기타 논의]**:
    * (위 4가지에 속하지 않는 기타 업무 논의)
    * (분류할 내용이 없다면 "없음"으로 표시)

**[출력 형식]** (이 형식을 반드시 지켜주세요):

## 🚀 [스페이스 이름 1]

### ‼️ 이슈/QA/장애
- (발견된 내용이 없다면 "없음"이라고 표시)

### ❓ 문의/질의
- (발견된 내용이 없다면 "없음"이라고 표시)

### ✍️ 기획/수정/정책
- (발견된 내용이 없다면 "없음"이라고 표시)

### 📢 공지/로그/일정
- (발견된 내용이 없다면 "없음"이라고 표시)

### 💬 기타 논의
- (발견된 내용이 없다면 "없음"이라고 표시)

---

**[중요 규칙]**
- 각 스페이스별로 5가지 카테고리를 모두 표시해야 합니다.
- 해당 카테고리에 내용이 없다면, 반드시 "없음"이라고 명시해 주세요.
- 단순 잡담, 인사, 농담 등은 완벽하게 무시합니다.
`;


/**
 * 메인 함수 (AI 봇)
 */
function dailyIssueSummary() {
  Logger.log("이슈 요약 작업을 시작합니다.");
  try {
    const allSpaces = listUserSpaces();
    if (!allSpaces || allSpaces.length === 0) {
      Logger.log("listUserSpaces()가 빈 목록(empty array)을 반환했습니다. 작업 종료.");
      return; 
    }

    const targetSpaces = allSpaces.filter(space => {
      if (space.spaceType !== 'SPACE' || !space.displayName) return false;
      return TARGET_SPACE_KEYWORDS.some(keyword => 
        space.displayName.includes(keyword)
      );
    });

    Logger.log(`필터링 후 ${targetSpaces.length}개의 스페이스를 대상으로 작업을 시작합니다.`);
    if (targetSpaces.length === 0) {
      Logger.log("대상 스페이스가 없습니다. (키워드: " + TARGET_SPACE_KEYWORDS.join(', ') + ")");
      return;
    }

    let allMessages = [];
    const filterTime = getFilterTime(HOURS_AGO);
    targetSpaces.forEach(space => {
      Logger.log(`[${space.displayName}] 스페이스의 메시지를 수집합니다.`);
      const messages = getRecentMessages(space.name, filterTime);
      if (messages.length > 0) {
        allMessages.push({
          spaceName: space.displayName,
          messages: messages.map(m => {
            const senderName = m.sender ? (m.sender.displayName || m.sender.name) : '알 수 없음';
            return `${senderName}: ${m.text}`;
          }).join('\n')
        });
      }
    });

    if (allMessages.length === 0) {
      Logger.log(`지난 ${HOURS_AGO}시간 동안 대상 스페이스에 새로운 메시지가 없습니다.`);
      return;
    }

    let combinedText = allMessages.map(item => {
      return `--- [${item.spaceName}] 스페이스 시작 ---\n${item.messages}\n--- [${item.spaceName}] 스페이스 종료 ---\n`;
    }).join('\n\n');

    const summary = summarizeWithGemini(combinedText);
    
    if (summary && summary.trim() !== "" && summary.trim() !== "특별한 이슈 없음" && !summary.startsWith("Vertex AI 응답 형식")) {
      writeToSheet(summary);
      Logger.log("요약 내용을 시트에 성공적으로 기록했습니다.");
    } else {
      Logger.log(`AI가 요약할 내용이 없거나 오류가 발생했습니다. (응답: ${summary})`);
    }

  } catch (e) {
    Logger.log(`오류 발생: ${e}`);
    Logger.log(e.stack); 
  }
}

/**
 * [Chat API] 스페이스 목록 가져오기
 */
function listUserSpaces() {
  const url = 'https://chat.googleapis.com/v1/spaces?pageSize=100';
  let spaces = [];
  let pageToken = null;
  const options = {
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
    },
    muteHttpExceptions: true,
  };

  try {
    do {
      const fullUrl = pageToken ? `${url}&pageToken=${pageToken}` : url;
      const response = UrlFetchApp.fetch(fullUrl, options);
      const responseCode = response.getResponseCode();
      const responseBody = response.getContentText();
      
      Logger.log(`[DEBUG] /v1/spaces API 응답 (HTTP ${responseCode})`);

      if (responseCode >= 400) {
        Logger.log(`스페이스 목록 가져오기 실패: ${responseBody}`);
        return [];
      }
      
      const data = JSON.parse(responseBody);
      if (data.spaces) {
        spaces = spaces.concat(data.spaces);
      }
      pageToken = data.nextPageToken;
    } while (pageToken);
    
    Logger.log(`API가 반환한 스페이스 ${spaces.length}개를 찾았습니다.`);
    return spaces;
  } catch (e) {
    Logger.log(`스페이스 목록 가져오기 실패 (UrlFetch): ${e}`);
    return [];
  }
}

/**
 * [Chat API] 최근 메시지 가져오기
 */
function getRecentMessages(spaceName, filterTime) {
  const encodedFilter = encodeURIComponent(`createTime > "${filterTime}"`);
  const url = `https://chat.googleapis.com/v1/${spaceName}/messages?filter=${encodedFilter}&pageSize=100`;
  let messages = [];
  let pageToken = null;
  const options = {
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
    },
    muteHttpExceptions: true,
  };

  try {
    do {
      const fullUrl = pageToken ? `${url}&pageToken=${pageToken}` : url;
      const response = UrlFetchApp.fetch(fullUrl, options);
      const responseCode = response.getResponseCode();

      if (responseCode >= 400) {
        Logger.log(`[${spaceName}] 메시지 가져오기 실패 (HTTP ${responseCode}): ${response.getContentText()}`);
        return [];
      }

      const data = JSON.parse(response.getContentText());
      if (data.messages) {
        const textMessages = data.messages.filter(m => m.text && !m.threadReply);
        messages = messages.concat(textMessages);
      }
      pageToken = data.nextPageToken;
    } while (pageToken);
    
    return messages.reverse();
  } catch (e) {
    Logger.log(`[${spaceName}] 메시지 가져오기 실패 (UrlFetch): ${e.message}`);
    return [];
  }
}


/**
 * [Gemini API - Vertex AI] AI 요약
 */
function summarizeWithGemini(text) {
  const PROJECT_ID = '965104926033'; 
  const LOCATION = 'us-central1';
  const MODEL_ID = 'gemini-2.0-flash-001'; 

  const vertexUrl = `https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/${MODEL_ID}:generateContent`;

  const fullPrompt = `${SYSTEM_PROMPT}\n\n[분석할 채팅 로그]\n${text}`;
  const payload = {
    "contents": [ { "role": "user", "parts": [{ "text": fullPrompt }] } ],
    "safetySettings": [
      { "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE" },
      { "category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE" } 
    ]
  };
  const options = {
    'method': 'post',
    'contentType': 'application/json',
    'payload': JSON.stringify(payload),
    'headers': {
      'Authorization': 'Bearer ' + ScriptApp.getOAuthToken()
    },
    'muteHttpExceptions': true
  };

  try {
    const response = UrlFetchApp.fetch(vertexUrl, options);
    const responseText = response.getContentText();
    const data = JSON.parse(responseText);

    if (data.candidates && data.candidates.length > 0 && data.candidates[0].content.parts) {
      return data.candidates[0].content.parts[0].text;
    } else {
      Logger.log(`Gemini API (Vertex) 응답 오류: ${responseText}`);
      return "Vertex AI 응답 형식이 올바르지 않습니다. 로그를 확인하세요.";
    }
  } catch (e) {
    Logger.log(`Gemini API (Vertex) 호출 실패: ${e}`);
    return null;
  }
}

/**
 * [Sheets API] 시트에 기록하기 (v2.1 - ISO 날짜 형식으로 수정됨)
 */
function writeToSheet(summary) {
  try {
    const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
    const today = new Date();
    
    // ISO 표준 문자열로 변환하여 저장 (날짜 인식률 100%)
    sheet.appendRow([today.toISOString(), "", summary]);

  } catch (e) {
    Logger.log(`시트 쓰기 실패: ${e}`);
  }
}

/**
 * 필터링할 기준 시간 생성
 */
function getFilterTime(hoursAgo) {
  const d = new Date();
  d.setHours(d.getHours() - hoursAgo); 
  return d.toISOString();
}

// --- (웹 앱 코드 시작) ---

/**
 * 웹 앱을 위한 doGet 함수
 */
function doGet(e) {
  return HtmlService.createTemplateFromFile('index')
      .evaluate()
      .setTitle('AI 이슈 요약 대시보드 (v2.2)') // <-- 버전 타이틀
      .setSandboxMode(HtmlService.SandboxMode.IFRAME);
}

/**
 * (CLEAN) HTML이 호출할 최종 함수 (v2.1 - 날짜 파싱 강화)
 */
function v5_getData() { 
  try {
    const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
    if (!sheet) {
      Logger.log("v5: 시트 이름을 찾을 수 없습니다: " + SHEET_NAME);
      return []; 
    }
    
    if (sheet.getLastRow() < 2) {
      Logger.log("v5: 시트에 데이터가 없습니다.");
      return [];
    }

    const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 3).getValues(); 
    
    const summaries = data.map(row => {
      const dateCell = row[0]; // (예: "2025-11-14T08:36:43.948Z")
      const summaryCell = row[2] || "";

      if (!dateCell || summaryCell.trim() === "") return null; 
      
      const dateObj = new Date(dateCell);

      if (isNaN(dateObj.getTime())) {
        Logger.log(`v5: 유효하지 않은 날짜 형식 감지: ${dateCell}`);
        return null;
      }

      const yyyy_mm_dd = Utilities.formatDate(dateObj, "Asia/Seoul", "yyyy-MM-dd");

      if (summaryCell.startsWith("Vertex AI 응답 형식")) {
        return null; 
      }

      return {
        displayDate: dateObj.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }),
        yyyy_mm_dd: yyyy_mm_dd, 
        summary: summaryCell
      };
    }).filter(row => row); 
    
    Logger.log(`v5: 유효한 데이터 ${summaries.length}건을 웹 앱으로 보냅니다.`);
    return summaries;
    
  } catch (e) {
    Logger.log(`v5_getData 오류: ${e}`);
    Logger.log(e.stack);
    return [];
  }
}