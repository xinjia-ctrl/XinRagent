import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const failures = [];

function read(path) {
  return readFileSync(resolve(root, path), "utf8");
}

function expectIncludes(path, snippets) {
  const content = read(path);
  for (const snippet of snippets) {
    if (!content.includes(snippet)) {
      failures.push(`${path} 缺少: ${snippet}`);
    }
  }
}

expectIncludes("src/router.tsx", [
  'path: "/login"',
  'path: "/chat"',
  'path: "/chat/:sessionId"',
  'path: "/admin"',
  'path: "dashboard"',
  'path: "knowledge"',
  'path: "knowledge/:kbId"',
  'path: "knowledge/:kbId/docs/:docId"',
  'path: "intent-tree"',
  'path: "intent-list"',
  'path: "intent-list/:id/edit"',
  'path: "ingestion"',
  'path: "traces"',
  'path: "traces/:traceId"',
  'path: "settings"',
  'path: "sample-questions"',
  'path: "mappings"',
  'path: "users"'
]);

expectIncludes("src/services/authService.ts", [
  '"/auth/login"',
  '"/auth/refresh"',
  '"/auth/logout"',
  '"/user/me"'
]);
expectIncludes("src/services/api.ts", [
  "refreshAuthToken",
  '"/auth/refresh"',
  "Bearer"
]);
expectIncludes("src/stores/authStore.ts", [
  "setRefreshToken",
  "refreshToken",
  "clearAuth"
]);

expectIncludes("src/services/knowledgeService.ts", [
  '"/knowledge-base"',
  '"/knowledge-base/chunk-strategies"',
  '"/knowledge-base/docs/search"',
  "chunk-logs"
]);
expectIncludes("src/services/ingestionService.ts", [
  '"/ingestion/pipelines"',
  '"/ingestion/tasks"',
  '"/ingestion/tasks/upload"'
]);
expectIncludes("src/services/intentTreeService.ts", [
  '"/intent-tree/trees"',
  '"/intent-tree/batch/enable"',
  '"/intent-tree/batch/disable"',
  '"/intent-tree/batch/delete"'
]);
expectIncludes("src/services/queryTermMappingService.ts", ['"/mappings"']);
expectIncludes("src/services/sampleQuestionService.ts", [
  '"/rag/sample-questions"',
  '"/sample-questions"'
]);
expectIncludes("src/services/ragTraceService.ts", [
  '"/rag/traces/runs"',
  "nodes"
]);
expectIncludes("src/services/settingsService.ts", ['"/rag/settings"']);
expectIncludes("src/services/userService.ts", ['"/users"', '"/user/password"']);
expectIncludes("src/services/dashboardService.ts", [
  '"/admin/dashboard/overview"',
  '"/admin/dashboard/performance"',
  '"/admin/dashboard/trends"'
]);

expectIncludes("src/pages/admin/dashboard/DashboardPage.tsx", ["getDashboardOverview", "getDashboardPerformance"]);
expectIncludes("src/pages/admin/knowledge/KnowledgeListPage.tsx", ["getKnowledgeBasesPage", "CreateKnowledgeBaseDialog"]);
expectIncludes("src/pages/admin/knowledge/KnowledgeDocumentsPage.tsx", ["getDocumentsPage", "uploadDocument"]);
expectIncludes("src/pages/admin/knowledge/KnowledgeChunksPage.tsx", ["getChunksPage", "updateChunk"]);
expectIncludes("src/pages/admin/ingestion/IngestionPage.tsx", ["getIngestionPipelines", "getIngestionTasks"]);
expectIncludes("src/pages/admin/traces/RagTracePage.tsx", ["getRagTraceRuns"]);
expectIncludes("src/pages/admin/traces/RagTraceDetailPage.tsx", ["getRagTraceDetail"]);
expectIncludes("src/pages/admin/settings/SystemSettingsPage.tsx", ["getSystemSettings"]);
expectIncludes("src/pages/admin/sample-questions/SampleQuestionPage.tsx", ["getSampleQuestions"]);
expectIncludes("src/pages/admin/query-term-mapping/QueryTermMappingPage.tsx", ["getQueryTermMappingsPage"]);
expectIncludes("src/pages/admin/users/UserListPage.tsx", ["getUsers"]);

if (failures.length > 0) {
  console.error("前端复刻验收失败:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("前端路由、服务端点、页面绑定和 refresh token 链路验收通过");
