/**
 * @file Code.gs
 * @description AI 회의록 도서관 시스템의 백엔드 로직을 담당합니다.
 * Google Sheets를 데이터베이스로 사용하고, OpenAI API를 호출하여 텍스트를 분석합니다.
 *
 * (수정 사항)
 * 1. AI에게 보고서 형식 (현황, 검토, 결정)의 상세 내용을 요청하도록 프롬프트 수정.
 * 2. saveLogToSheet 함수에서 organizedContent가 배열일 경우 문자열로 강제 변환하여 저장 오류 방지.
 */

// ========== 설정 (Constants) ==========

const SHEET_NAME = '시트1'; 
const SPREADSHEET_ID = '1HYC0D0ow3kWdf-H6C0fNwNRCwn0tB-aTFgHk24KpHRI'; 
const API_KEY_PROPERTY = 'OPENAI_API_KEY'; 
const OPENAI_ENDPOINT = 'https://api.openai.com/v1/chat/completions';
// 토큰 길이 초과 문제 해결을 위해 gpt-4o 모델 사용 (더 비쌈, 잔액 확인 필수)
const MODEL_NAME = 'gpt-4o'; 

/**
 * 활성 Google Sheets를 가져옵니다.
 */
function getSpreadsheet() {
  try {
    return SpreadsheetApp.openById(SPREADSHEET_ID); 
  } catch (e) {
    Logger.log('Error opening spreadsheet: ' + e.toString());
    return null;
  }
}

/**
 * 웹 앱이 실행될 때 호출되어 Index.html을 제공합니다.
 */
function doGet() {
  const template = HtmlService.createTemplateFromFile('Index');
  return template.evaluate()
      .setTitle('AI 회의록 도서관')
      .setSandboxMode(HtmlService.SandboxMode.IFRAME);
}

// ========== 데이터베이스 (Google Sheets) 관련 함수 ==========

/**
 * Google Sheets에서 모든 회의록 목록을 가져옵니다.
 */
function getAllMeetingLogs() {
  const ss = getSpreadsheet();
  if (!ss) return [];

  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) return []; 

  // A열(날짜)부터 G열(원본내용)까지 7개 컬럼을 모두 가져옵니다.
  const dataRange = sheet.getRange(2, 1, sheet.getLastRow() - 1, 7); 
  return dataRange.getValues().map((row, index) => {
    return {
      id: index + 2, 
      date: Utilities.formatDate(new Date(row[0]), Session.getScriptTimeZone(), 'yyyy-MM-dd'), 
      title: row[1],
      summary: row[2],
      tags: row[3],
      tasks: row[4],
      organizedContent: row[5], // '정리된 내용'
      transcript: row[6]
    };
  }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()); 
}

/**
 * 키워드를 포함하는 회의록 목록을 검색합니다.
 */
function searchLogs(keyword) {
  const allLogs = getAllMeetingLogs();
  if (!keyword || keyword.trim() === '') {
    return allLogs; 
  }

  const searchKeyword = keyword.trim().toLowerCase();
  
  return allLogs.filter(log => {
    return log.title.toLowerCase().includes(searchKeyword) ||
           log.summary.toLowerCase().includes(searchKeyword) ||
           log.tags.toLowerCase().includes(searchKeyword);
  });
}

/**
 * 분석 결과를 Sheets에 저장합니다. (오류 방지 로직 추가됨)
 */
function saveLogToSheet(date, title, summary, tags, tasks, organizedContent, transcript) {
  const ss = getSpreadsheet();
  if (!ss) throw new Error('스프레드시트를 찾을 수 없습니다.');

  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) throw new Error(`${SHEET_NAME} 시트를 찾을 수 없습니다.`);

  const tagsString = tags.join(', ');
  const tasksString = tasks.join('\n'); 

  // [중요 수정] organizedContent가 배열로 넘어올 경우, 줄바꿈으로 합쳐서 문자열로 저장합니다.
  const contentToSave = Array.isArray(organizedContent) ? organizedContent.join('\n\n') : organizedContent;
  
  // Sheets에 새로운 행 추가.
  // [A열: 날짜, B열: 제목, C열: 요약, D열: 태그, E열: 할일, F열: 정리된내용, G열: 원본내용]
  sheet.appendRow([date, title, summary, tagsString, tasksString, contentToSave, transcript]);
}

// ========== OpenAI API 호출 함수 (핵심) ==========

/**
 * OpenAI API를 호출하여 녹취록을 분석하고 결과를 Sheets에 저장합니다.
 */
function processTranscript(date, title, transcript) {
  try {
    const apiKey = PropertiesService.getScriptProperties().getProperty(API_KEY_PROPERTY);
    if (!apiKey) {
      throw new Error('스크립트 속성(OPENAI_API_KEY)에 API 키가 설정되어 있지 않습니다.');
    }

    if (!transcript || transcript.length < 50) { 
        throw new Error('녹취록 원문 내용이 너무 짧거나 비어있습니다. (최소 50자 이상)');
    }

    // [중요 수정] 시스템 프롬프트를 보고서 형식에 맞춰 강화합니다.
    const systemPrompt = `당신은 회의록을 분석하고 공식적인 보고서 형식으로 변환하는 AI 전문가입니다.
사용자에게서 받은 녹취록을 분석하여 다음 JSON 형식으로만 응답해야 합니다. 다른 설명이나 텍스트는 포함하지 마세요.

JSON 스키마 설명:
- "summary": 회의의 가장 핵심적인 내용을 100자 이내로 요약.
- "organized_content": 회의 내용을 사용자의 예시처럼 다음과 같은 명확한 구조를 가진 Markdown 형식의 텍스트로 상세하게 정리합니다.
  1. 주요 현황 및 이슈 제기
  2. 법률적 또는 기술적 검토 의견
  3. 결정 사항 및 후속 조치
- "tags": 회의 주제에 맞는 핵심 키워드 3~5개.
- "tasks": 회의에서 결정된 주요 할 일(Action Item) 목록을 2~5개 추출하고 주체를 명시.

예시:
"organized_content": "1. 주요 현황 및 이슈 제기\\n- 미접속 유저의 환불 문제가 지속적으로 제기됨.\\n- 환불 정책의 기준을 명확히 해야 함.\\n\\n2. 법률적 또는 기술적 검토 의견\\n- (검토 의견 A)...\\n- (검토 의견 B)...\\n\\n3. 결정 사항 및 후속 조치\\n- (결정 사항)...\\n- (후속 조치)..."

{
  "summary": "...",
  "organized_content": "[여기에 모든 보고서 내용을 포함합니다]", 
  "tags": ["...", "..."],
  "tasks": ["...", "..."]
}`;

    const payload = {
      model: MODEL_NAME,
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: `회의 제목: ${title}\n\n녹취록:\n${transcript}` }
      ],
      response_format: { type: "json_object" }, 
      temperature: 0.2, 
    };

    const options = {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'Authorization': `Bearer ${apiKey}`
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true 
    };
    
    // API 호출
    const response = UrlFetchApp.fetch(OPENAI_ENDPOINT, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();

    if (responseCode !== 200) {
      let errorMessage = `응답 코드: ${responseCode}. 자세한 내용은 로그를 확인하세요.`;
      try {
        const errorJson = JSON.parse(responseText);
        if (errorJson && errorJson.error && errorJson.error.message) {
          errorMessage = `API 오류: ${errorJson.error.message} (코드: ${responseCode})`;
        }
      } catch (e) {
        // ...
      }
      
      Logger.log(`API Error Code: ${responseCode}, Response: ${responseText}`);
      throw new Error(`OpenAI API 호출에 실패했습니다. ${errorMessage}`);
    }

    const jsonResponse = JSON.parse(responseText);
    const contentText = jsonResponse.choices?.[0]?.message?.content;
    
    if (!contentText) {
         throw new Error('API 응답에서 내용(content)을 찾을 수 없습니다.');
    }
    
    const analysisResult = JSON.parse(contentText);
    
    // Sheets에 저장
    saveLogToSheet(
      date,
      title,
      analysisResult.summary || '분석 실패',
      analysisResult.tags || [],
      analysisResult.tasks || [],
      analysisResult.organized_content || '정리된 내용 없음', 
      transcript
    );

    return { success: true, message: '회의록 분석 및 저장이 완료되었습니다. 목록을 새로고침합니다.' };

  } catch (error) {
    Logger.log('처리 중 오류 발생: ' + error.toString());
    return { success: false, message: '오류가 발생했습니다: ' + error.message };
  }
}