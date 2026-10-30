import { useEffect, useRef, useState } from "react";

import {
  Activity,
  Bot,
  Bug,
  CheckCircle2,
  ChevronDown,
  Code2,
  FileCode2,
  Lightbulb,
  Loader2,
  MessageSquare,
  Paperclip,
  Play,
  Send,
  Settings2,
  Sparkles,
  TestTube2,
  Wrench,
  Zap,
} from "lucide-react";

import { ApiRequestError } from "../../services/api";
import {
  sendAIChat,
  type AIProvider,
} from "../../services/aiApi";

import {
  analyzeRepository,
  type RepositoryAnalyzeResponse,
} from "../../services/repositoryApi";
import { repositoryStore } from "../stores/repositoryStore";
import { editorStore } from "../stores/editorStore";
import {
  saveGeneratedTestCode,
  generateTestCode,
  generateTests,
  type GeneratedTestCode,
  type GeneratedTestCase,
  type TestCodeGenerationRequest,
  type TestingFramework,
  type TestType,
} from "../../services/testingApi";

type AITab =
  | "chat"
  | "code"
  | "tests"
  | "insights";

type AIAction =
  | "analyze-repository"
  | "generate-tests"
  | "generate-automation"
  | "analyze-failure"
  | "self-heal"
  | "explain-code";

type ScenarioTypeSelection =
  | "all"
  | "functional"
  | "integration"
  | "api"
  | "regression"
  | "boundary"
  | "negative"
  | "exception"
  | "edge_case";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  action?: AIAction;
}

interface AIActionItem {
  id: AIAction;
  title: string;
  description: string;
  icon: typeof FileCode2;
}

interface RepositoryAnalysis {
  architecture: string;
  technologies: string[];
  dependencies: string[];
  important_modules: string[];
  apis: string[];
  configurations: string[];
  existing_tests: string[];
  automation_assets: string[];
  testing_areas: string[];
}

interface AIAnalysisResponse {
  task: string;
  provider: string;
  model: string;
  content: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
  analysis?: RepositoryAnalysis | null;
}

const actions: AIActionItem[] = [
  {
    id: "analyze-repository",
    title: "Analyze Repository",
    description:
      "Understand project structure and dependencies",
    icon: FileCode2,
  },
  {
    id: "generate-tests",
    title: "Generate Test Cases",
    description:
      "Create repository-aware test scenarios",
    icon: Wrench,
  },
  {
    id: "generate-automation",
    title: "Generate Automation",
    description:
      "Generate Selenium or Playwright tests",
    icon: Code2,
  },
  {
    id: "analyze-failure",
    title: "Analyze Failure",
    description:
      "Perform root cause analysis",
    icon: Bug,
  },
  {
    id: "self-heal",
    title: "Self-Heal Test",
    description:
      "Repair and re-run failed automation",
    icon: Sparkles,
  },
  {
    id: "explain-code",
    title: "Explain Code",
    description:
      "Explain selected code or the current file",
    icon: Lightbulb,
  },
];

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: "assistant",
    content:
      "I can analyze your repository, generate tests, create automation scripts, analyze failures, and improve test coverage.",
  },
];

const taskMap: Record<
  AIAction,
  | "analyze_repository"
  | "generate_tests"
  | "generate_automation"
  | "analyze_failure"
  | "self_heal"
  | "explain_code"
> = {
  "analyze-repository":
    "analyze_repository",

  "generate-tests":
    "generate_tests",

  "generate-automation":
    "generate_automation",

  "analyze-failure":
    "analyze_failure",

  "self-heal":
    "self_heal",

  "explain-code":
    "explain_code",
};

const promptMap: Record<
  AIAction,
  string
> = {
  "analyze-repository":
    "Analyze this software repository for intelligent software testing. Identify its architecture, technologies, dependencies, important modules, APIs, configurations, existing tests, automation assets, and potential testing areas.",

  "generate-tests":
    "Generate comprehensive repository-aware test scenarios covering functional, integration, API, regression, boundary, negative, exception, and edge-case testing. Explain the most important scenarios for this repository.",

  "generate-automation":
    "Design executable automation tests for this repository. Identify appropriate Selenium or Playwright scenarios, target components, locators, workflows, and assertions.",

  "analyze-failure":
    "Analyze the repository and available testing context for likely failure causes. Identify possible application defects, UI changes, invalid locators, API changes, configuration problems, automation failures, and other root causes.",

  "self-heal":
    "Identify automation artifacts that may require self-healing. Explain likely repair strategies for locator changes, UI changes, API changes, configuration problems, and automation failures.",

  "explain-code":
    "Explain the selected or current file code. Describe its purpose, main logic, functions or classes, dependencies, and execution flow based only on the actual source. Do not modify or execute the code, and do not expose secrets.",
};

const allTestTypes: TestType[] = [
  "functional",
  "integration",
  "api",
  "regression",
  "boundary",
  "negative",
  "exception",
  "edge_case",
];

const integrationPrompt =
  "Generate integration test scenarios grounded in the supplied repository context. Focus on interactions between evidenced components, the data or control flow across their boundaries, concrete setup and steps, and observable expected results. Do not assume components or dependencies that are not present in the context.";

const apiPrompt =
  "Generate API test scenarios only from API routes or API specifications evidenced by the supplied repository context. Use the actual endpoint paths and HTTP methods. Describe request inputs and observable response behavior, including status codes, validation, or authentication only when supported by the evidence. Do not invent endpoint details or produce UI-only scenarios.";

const regressionPrompt =
  "Generate regression test scenarios grounded in current repository code, existing tests, and documented contracts. Identify the evidenced existing behavior being protected and provide reproducible steps with observable expected results. This workflow does not provide Git history, prior test results, or before-and-after code unless included in repository context; do not claim a specific change, bug fix, or historical regression risk without evidence.";

const boundaryPrompt =
  "Generate boundary test scenarios only from explicit constraints in the supplied repository context, such as minimums, maximums, ranges, thresholds, size restrictions, pagination limits, or date/time constraints. Use documented values to cover below, at, and above boundaries where applicable, with reproducible steps and observable expected results. Do not invent limits or produce unrelated scenario categories.";

const negativePrompt =
  "Generate negative test scenarios only from validation, rejection, authorization, or error behavior explicitly evidenced in the supplied repository context. Use supported invalid or disallowed inputs and verify the documented observable response. Include status codes or error details only when evidenced. Do not invent credentials, constraints, or error behavior, and avoid unrelated scenario categories.";

const exceptionPrompt =
  "Generate exception test scenarios only from exception types, raising/catching behavior, propagation, cleanup, or failure paths explicitly evidenced in repository code or tests. Verify documented observable behavior when the evidenced exception path occurs. Do not invent exception classes, messages, or outcomes, and keep scenarios distinct from negative inputs, boundaries, and edge conditions.";

const edgeCasePrompt =
  "Generate edge-case scenarios only from unusual combinations, optional states, fallbacks, or conditional interactions explicitly evidenced in repository code, tests, or documentation. Explain the unusual condition and verify observable behavior with reproducible steps. Do not produce generic lists or invent behavior, and keep scenarios distinct from boundaries, negative inputs, and exceptions.";

function mapProvider(
  provider: string,
): AIProvider {
  switch (provider) {
    case "GPT":
      return "gpt";

    case "Gemini":
      return "gemini";

    case "Llama":
      return "llama";

    case "DeepSeek":
      return "deepseek";

    default:
      return "auto";
  }
}

export default function AIPanel() {
  const [activeTab, setActiveTab] =
    useState<AITab>("chat");

  const [provider, setProvider] =
    useState("Multi-LLM Orchestrator");

  const [input, setInput] =
    useState("");

  const [messages, setMessages] =
    useState<ChatMessage[]>(
      initialMessages,
    );

  const [isWorking, setIsWorking] =
    useState(false);

  const isWorkingRef = useRef(false);

  const [lastAction, setLastAction] =
    useState<AIAction | null>(null);

  const messageIdRef = useRef(2);

  const executeActionRef = useRef<
    (
      action: AIAction,
      testTypes?: TestType[],
    ) => Promise<void>
  >(async () => undefined);

  const [analysis, setAnalysis] =
    useState<RepositoryAnalysis | null>(
      null,
    );

  const [analysisProvider, setAnalysisProvider] =
    useState<string | null>(null);

  const [analysisModel, setAnalysisModel] =
    useState<string | null>(null);

  const [analysisError, setAnalysisError] =
    useState<string | null>(null);

  const [generatedTests, setGeneratedTests] =
    useState<GeneratedTestCase[]>([]);

  const [testGenerationError, setTestGenerationError] =
    useState<string | null>(null);

  const [testGenerationCount, setTestGenerationCount] =
    useState(5);

  const [scenarioTypeSelection, setScenarioTypeSelection] =
    useState<ScenarioTypeSelection>("all");

  const [hasGeneratedScenarios, setHasGeneratedScenarios] =
    useState(false);

  const [frameworkSelection, setFrameworkSelection] =
    useState<TestingFramework | "">("");

  const [frameworkRecommendation, setFrameworkRecommendation] =
    useState<RepositoryAnalyzeResponse | null>(null);

  const [isRecommendingFramework, setIsRecommendingFramework] =
    useState(false);

  const [frameworkRecommendationError, setFrameworkRecommendationError] =
    useState<string | null>(null);

  const [isGeneratingCode, setIsGeneratingCode] =
    useState(false);

  const [generatedCode, setGeneratedCode] =
    useState<GeneratedTestCode | null>(null);

  const [isSavingGeneratedCode, setIsSavingGeneratedCode] =
    useState(false);

  const [savedGeneratedCodeFile, setSavedGeneratedCodeFile] =
    useState<string | null>(null);

  const [codeGenerationError, setCodeGenerationError] =
    useState<string | null>(null);

  const [codeSaveError, setCodeSaveError] =
    useState<string | null>(null);
  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);

  /*
   * Keep chat scrolled to the latest message.
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isWorking]);

  /*
   * Listen for commands coming from
   * the Run menu / other TestForge UI.
   */
  useEffect(() => {
    const handleGenerateTests = () => {
      void executeActionRef.current("generate-tests");
    };

    const handleAnalyzeFailure = () => {
      void executeActionRef.current("analyze-failure");
    };

    const handleSelfHeal = () => {
      void executeActionRef.current("self-heal");
    };

    const handleExplainCode = () => {
      void executeActionRef.current("explain-code");
    };

    const handleAnalytics = () => {
      setActiveTab("insights");
    };

    const handleOpenAI = () => {
      setActiveTab("chat");
    };

    window.addEventListener(
      "testforge:generate-tests",
      handleGenerateTests,
    );

    window.addEventListener(
      "testforge:analyze-failure",
      handleAnalyzeFailure,
    );

    window.addEventListener(
      "testforge:self-heal",
      handleSelfHeal,
    );

    window.addEventListener(
      "testforge:explain-code",
      handleExplainCode,
    );

    window.addEventListener(
      "testforge:analytics",
      handleAnalytics,
    );

    window.addEventListener(
      "testforge:open-ai",
      handleOpenAI,
    );

    return () => {
      window.removeEventListener(
        "testforge:generate-tests",
        handleGenerateTests,
      );

      window.removeEventListener(
        "testforge:analyze-failure",
        handleAnalyzeFailure,
      );

      window.removeEventListener(
        "testforge:self-heal",
        handleSelfHeal,
      );

      window.removeEventListener(
        "testforge:explain-code",
        handleExplainCode,
      );

      window.removeEventListener(
        "testforge:analytics",
        handleAnalytics,
      );

      window.removeEventListener(
        "testforge:open-ai",
        handleOpenAI,
      );
    };
  }, []);

  /*
   * Execute an actual TestForge AI action.
   */
  const executeAction = async (
    action: AIAction,
    requestedTestTypes?: TestType[],
  ) => {
    if (isWorkingRef.current) {
      return;
    }

    const selectedAction =
      actions.find(
        (item) => item.id === action,
      );

    if (!selectedAction) {
      return;
    }

    const repositoryPath =
      repositoryStore.getState().rootPath;

    const activeEditorTab =
      editorStore.getState().tabs.find(
        (tab) =>
          tab.id ===
          editorStore.getState().activeTabId,
      ) ?? null;
    const selectedCode =
      editorStore.getSelectedCode();
    const codeToExplain =
      selectedCode.trim()
        ? selectedCode
        : activeEditorTab?.content ?? "";

    setActiveTab("chat");
    setLastAction(action);

    if (action === "explain-code") {
      if (!codeToExplain.trim()) {
        const assistantMessage: ChatMessage =
          {
            id: messageIdRef.current++,
            role: "assistant",
            content:
              "No code is available to explain. Open a file or select code in the editor.",
            action,
          };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);

        return;
      }
    } else if (!repositoryPath) {
      const assistantMessage: ChatMessage =
        {
          id: messageIdRef.current++,
          role: "assistant",
          content:
            "Please open a repository first. TestForge AI needs repository context to perform this action.",
          action,
        };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);

      return;
    }

    isWorkingRef.current = true;
    setIsWorking(true);

    const userMessage: ChatMessage = {
      id: messageIdRef.current++,
      role: "user",
      content: selectedAction.title,
      action,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    window.dispatchEvent(
      new CustomEvent(
        `testforge:ai:${action}`,
      ),
    );

    try {
      const selectedProvider =
        mapProvider(provider);

      if (action === "generate-tests") {
        setActiveTab("tests");
        setTestGenerationError(null);

        const testTypes =
          requestedTestTypes ??
          (scenarioTypeSelection === "all"
            ? allTestTypes
            : [scenarioTypeSelection]);
        const requestPrompt =
          testTypes.length === 1 &&
          testTypes[0] === "integration"
            ? integrationPrompt
            : testTypes.length === 1 &&
                testTypes[0] === "api"
              ? apiPrompt
            : testTypes.length === 1 &&
                testTypes[0] === "regression"
              ? regressionPrompt
            : testTypes.length === 1 &&
                testTypes[0] === "boundary"
              ? boundaryPrompt
            : testTypes.length === 1 &&
                testTypes[0] === "negative"
              ? negativePrompt
            : testTypes.length === 1 &&
                testTypes[0] === "exception"
              ? exceptionPrompt
            : testTypes.length === 1 &&
                testTypes[0] === "edge_case"
              ? edgeCasePrompt
            : promptMap[action];

        const response = await generateTests(
          repositoryPath!,
          requestPrompt,
          testTypes,
          testGenerationCount,
        );

        const testCases = response.test_cases;
        setGeneratedTests(testCases);
        setHasGeneratedScenarios(true);

        const generatedCount = testCases.length;
        const assistantMessage: ChatMessage = {
          id: messageIdRef.current++,
          role: "assistant",
          content:
            `Generated ${generatedCount} repository-aware test case${generatedCount === 1 ? "" : "s"}.\n\n` +
            `Open the Tests tab to review the scenarios.`,
          action,
        };

        setMessages((current) => [...current, assistantMessage]);
        return;
      }

      const response =
        (await sendAIChat({
          task: taskMap[action],
          prompt: promptMap[action],
          provider: selectedProvider,
          fallback_providers: [
            "gpt",
            "gemini",
            "llama",
            "deepseek",
            "mock",
          ],
          repository_path: repositoryPath,
          context:
            action === "explain-code"
              ? codeToExplain
              : null,
          temperature: 0.2,
          max_tokens: 4096,
        })) as AIAnalysisResponse;

      /*
       * Store structured repository analysis.
       *
       * The backend only returns this field for
       * repository analysis, so other actions
       * leave the existing analysis untouched.
       */
      if (
        action === "analyze-repository"
      ) {
        if (response.analysis) {
          setAnalysis(response.analysis);
          setAnalysisProvider(
            response.provider,
          );
          setAnalysisModel(
            response.model,
          );
          setAnalysisError(null);
          setActiveTab("insights");
        } else {
          setAnalysisError(
            "The AI response did not contain structured repository analysis.",
          );
        }
      }

      const assistantMessage:
        ChatMessage = {
        id: messageIdRef.current++,
        role: "assistant",
        content:
          `${response.content}\n\n` +
          `Provider: ${response.provider}\n` +
          `Model: ${response.model}`,
        action,
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "AI request failed.";

      if (action === "analyze-repository") {
        setAnalysisError(message);
      }

      if (action === "generate-tests") {
        setTestGenerationError(message);
      }

      const assistantMessage:
        ChatMessage = {
        id: messageIdRef.current++,
        role: "assistant",
        content:
          `TestForge AI request failed.\n\n${message}`,
        action,
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);
    } finally {
      isWorkingRef.current = false;
      setIsWorking(false);
    }
  };

  useEffect(() => {
    executeActionRef.current = executeAction;
  });

  const handleRecommendFramework = async () => {
    const repositoryPath = repositoryStore.getState().rootPath;
    if (!repositoryPath) {
      setFrameworkRecommendationError(
        "Open a repository before requesting a framework recommendation.",
      );
      return;
    }

    setIsRecommendingFramework(true);
    setFrameworkRecommendationError(null);
    setFrameworkRecommendation(null);
    try {
      const recommendation = await analyzeRepository(repositoryPath);
      setFrameworkRecommendation(recommendation);
      setFrameworkSelection(
        recommendation.recommended_test_framework ?? "",
      );
      if (!recommendation.recommended_test_framework) {
        setFrameworkRecommendationError(
          "No supported test framework could be recommended from the detected repository evidence.",
        );
      }
    } catch (error) {
      setFrameworkRecommendationError(
        error instanceof Error
          ? error.message
          : "Framework recommendation failed.",
      );
    } finally {
      setIsRecommendingFramework(false);
    }
  };

  const handleGenerateExecutableTests = async () => {
    const repositoryPath = repositoryStore.getState().rootPath;
    if (!repositoryPath || !frameworkSelection || generatedTests.length === 0) {
      return;
    }

    const supportedFrameworks =
      frameworkRecommendation?.supported_test_frameworks ?? [];
    if (!supportedFrameworks.includes(frameworkSelection)) {
      setCodeGenerationError(
        "The selected framework is not supported by the analyzed repository evidence.",
      );
      return;
    }

    const repositoryLanguages =
      frameworkRecommendation?.supported_test_languages ?? [];
    const language: TestCodeGenerationRequest["language"] | null =
      frameworkSelection === "pytest"
        ? "python"
        : repositoryLanguages.includes("TypeScript")
          ? "typescript"
          : repositoryLanguages.includes("JavaScript")
            ? "javascript"
            : repositoryLanguages.includes("Python")
              ? "python"
              : null;
    if (!language) {
      setCodeGenerationError(
        "Analyze the repository to detect a compatible Python, JavaScript, or TypeScript language before generating code.",
      );
      return;
    }

    if (
      frameworkSelection === "pytest" &&
      (!repositoryLanguages.includes("Python") ||
        language !== "python")
    ) {
      setCodeGenerationError(
        "Pytest requires detected Python project evidence.",
      );
      return;
    }

    const fileExtension =
      language === "python"
        ? "py"
        : language === "typescript"
          ? "ts"
          : "js";
    const outputFile =
      frameworkSelection === "pytest"
        ? `tests/test_testforge_generated_${Date.now()}.${fileExtension}`
        : `tests/testforge-generated-${Date.now()}.spec.${fileExtension}`;

    setIsGeneratingCode(true);
    setCodeGenerationError(null);
    setCodeSaveError(null);
    setGeneratedCode(null);
    setSavedGeneratedCodeFile(null);
    try {
      const response = await generateTestCode({
        repository_path: repositoryPath,
        test_cases: generatedTests,
        framework: frameworkSelection,
        language,
        output_file: outputFile,
      });
      const generatedFile = response.generated_files[0];
      if (
        response.total_files !== 1 ||
        response.generated_files.length !== 1 ||
        !generatedFile?.file_path ||
        !generatedFile.code.trim() ||
        generatedFile.framework !== frameworkSelection ||
        generatedFile.language !== language ||
        generatedFile.test_case_ids.length !== generatedTests.length ||
        generatedFile.test_case_ids.some(
          (id, index) => id !== generatedTests[index]?.id,
        )
      ) {
        throw new Error(
          "The generated-code response was incomplete or invalid.",
        );
      }
      setGeneratedCode(generatedFile);
      if (response.context_warning) {
        setCodeGenerationError(response.context_warning);
      }
    } catch (error) {
      setCodeGenerationError(
        error instanceof Error
          ? error.message
          : "Executable test generation failed.",
      );
    } finally {
      setIsGeneratingCode(false);
    }
  };

  const handleSaveGeneratedCode = async () => {
    const repositoryPath = repositoryStore.getState().rootPath;
    if (!repositoryPath || !generatedCode) {
      return;
    }

    setIsSavingGeneratedCode(true);
    setCodeSaveError(null);
    try {
      let overwrite = false;
      let savedFile: Awaited<ReturnType<typeof saveGeneratedTestCode>>;

      while (true) {
        try {
          savedFile = await saveGeneratedTestCode({
            repository_path: repositoryPath,
            generated_file: generatedCode,
            overwrite,
          });
          break;
        } catch (error) {
          if (error instanceof ApiRequestError && error.status === 409) {
            if (
              !window.confirm(
                "A file already exists at this location. Replace its contents?",
              )
            ) {
              setCodeSaveError(
                "The existing file was preserved. Choose a different generated file name to save a new copy.",
              );
              return;
            }
            overwrite = true;
            continue;
          }
          throw error;
        }
      }

      if (
        !savedFile.file_path ||
        !savedFile.relative_path ||
        savedFile.code !== generatedCode.code
      ) {
        throw new Error(
          "The save response did not include matching saved-file metadata and content.",
        );
      }

      const fileName =
        savedFile.file_path.split(/[\\/]/).pop() ??
        savedFile.relative_path.split(/[\\/]/).pop();
      if (!fileName) {
        throw new Error(
          "The saved file response did not include a file name.",
        );
      }

      setSavedGeneratedCodeFile(savedFile.file_path);
      window.dispatchEvent(
        new CustomEvent("testforge:generated-file-saved", {
          detail: { path: savedFile.file_path },
        }),
      );
      window.dispatchEvent(
        new CustomEvent("testforge:open-file", {
          detail: {
            path: savedFile.file_path,
            name: fileName,
            content: savedFile.code,
          },
        }),
      );
    } catch (error) {
      setCodeSaveError(
        error instanceof Error
          ? error.message
          : "Generated test file could not be saved.",
      );
    } finally {
      setIsSavingGeneratedCode(false);
    }
  };

  /*
   * Send a normal AI chat message.
   */
  const handleSendMessage =
    async () => {
      const trimmed =
        input.trim();

      if (
        !trimmed ||
        isWorkingRef.current
      ) {
        return;
      }

      const repositoryPath =
        repositoryStore.getState()
          .rootPath;

      setActiveTab("chat");

      if (!repositoryPath) {
        setInput("");

        const assistantMessage:
          ChatMessage = {
          id: messageIdRef.current++,
          role: "assistant",
          content:
            "Please open a repository first. TestForge AI uses repository-aware context to answer your questions.",
        };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);

        return;
      }

      setInput("");
      isWorkingRef.current = true;
      setIsWorking(true);

      const userMessage:
        ChatMessage = {
        id: messageIdRef.current++,
        role: "user",
        content: trimmed,
      };

      setMessages((current) => [
        ...current,
        userMessage,
      ]);

      window.dispatchEvent(
        new CustomEvent(
          "testforge:ai:chat",
          {
            detail: {
              message: trimmed,
              provider,
              repositoryPath,
            },
          },
        ),
      );

      try {
        const response =
          await sendAIChat({
            task: "generate_tests",

            prompt: trimmed,

            provider:
              mapProvider(provider),

            fallback_providers: [
              "gpt",
              "gemini",
              "llama",
              "deepseek",
              "mock",
            ],

            repository_path:
              repositoryPath,

            temperature: 0.2,

            max_tokens: 4096,
          });

        const assistantMessage:
          ChatMessage = {
          id: messageIdRef.current++,
          role: "assistant",
          content:
            `${response.content}\n\n` +
            `Provider: ${response.provider}\n` +
            `Model: ${response.model}`,
        };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "AI request failed.";

        const assistantMessage:
          ChatMessage = {
          id: messageIdRef.current++,
          role: "assistant",
          content:
            `TestForge AI request failed.\n\n${message}`,
        };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);
      } finally {
        isWorkingRef.current = false;
        setIsWorking(false);
      }
    };

  /*
   * Enter to send.
   */
  const handleInputKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      void handleSendMessage();
    }
  };

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col bg-[#0d1117] text-[#c9d1d9]">

      {/* HEADER */}

      <div className="flex h-10 shrink-0 items-center border-b border-[#252a33] px-3">
        <Bot
          size={15}
          className="mr-2 text-blue-400"
        />

        <span className="text-[12px] font-semibold text-white">
          TESTFORGE AI
        </span>

        <div className="ml-auto flex items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              isWorking
                ? "animate-pulse bg-yellow-400"
                : "bg-emerald-400"
            }`}
          />

          <span className="text-[10px] text-[#8b949e]">
            {isWorking
              ? "Working..."
              : "Ready"}
          </span>
        </div>
      </div>

      {/* TABS */}

      <div className="flex h-10 shrink-0 border-b border-[#252a33]">
        <AITabButton
          active={
            activeTab === "chat"
          }
          icon={
            <MessageSquare
              size={13}
            />
          }
          label="Chat"
          onClick={() =>
            setActiveTab("chat")
          }
        />

        <AITabButton
          active={
            activeTab === "code"
          }
          icon={
            <Code2 size={13} />
          }
          label="Code"
          onClick={() =>
            setActiveTab("code")
          }
        />

        <AITabButton
          active={
            activeTab === "tests"
          }
          icon={
            <TestTube2
              size={13}
            />
          }
          label="Tests"
          onClick={() =>
            setActiveTab("tests")
          }
        />

        <AITabButton
          active={
            activeTab === "insights"
          }
          icon={
            <Activity
              size={13}
            />
          }
          label="Insights"
          onClick={() =>
            setActiveTab(
              "insights",
            )
          }
        />
      </div>

      {/* CONTENT */}

      <div className="min-h-0 flex-1 overflow-hidden">

        {activeTab ===
          "chat" && (
          <ChatView
            messages={
              messages
            }
            isWorking={
              isWorking
            }
            messagesEndRef={
              messagesEndRef
            }
          />
        )}

        {activeTab ===
          "code" && (
          <CodeView
            onExplainCode={() =>
              void executeAction("explain-code")
            }
          />
        )}

        {activeTab ===
          "tests" && (
          <TestsView
            onRunAction={executeAction}
            generatedTests={generatedTests}
            generationCount={testGenerationCount}
            onGenerationCountChange={setTestGenerationCount}
            scenarioTypeSelection={scenarioTypeSelection}
            onScenarioTypeSelectionChange={setScenarioTypeSelection}
            hasGeneratedScenarios={hasGeneratedScenarios}
            isWorking={isWorking}
            error={testGenerationError}
            frameworkSelection={frameworkSelection}
            onFrameworkSelectionChange={setFrameworkSelection}
            frameworkRecommendation={frameworkRecommendation}
            isRecommendingFramework={isRecommendingFramework}
            frameworkRecommendationError={frameworkRecommendationError}
            onRecommendFramework={handleRecommendFramework}
            isGeneratingCode={isGeneratingCode}
            generatedCode={generatedCode}
            savedGeneratedCodeFile={savedGeneratedCodeFile}
            codeGenerationError={codeGenerationError}
            isSavingGeneratedCode={isSavingGeneratedCode}
            codeSaveError={codeSaveError}
            onGenerateExecutableTests={handleGenerateExecutableTests}
            onSaveGeneratedCode={handleSaveGeneratedCode}
          />
        )}

        {activeTab ===
          "insights" && (
          <InsightsView
            analysis={
              analysis
            }
            provider={
              analysisProvider
            }
            model={
              analysisModel
            }
            error={
              analysisError
            }
            isWorking={
              isWorking
            }
            onAnalyze={() =>
              void executeAction(
                "analyze-repository",
              )
            }
          />
        )}

      </div>

      {/* ACTIONS */}

      {activeTab ===
        "chat" && (
        <>
          <div className="shrink-0 border-t border-[#252a33]">
            <div className="px-3 py-2">

              <div className="mb-2 flex items-center gap-2">
                <Lightbulb
                  size={12}
                  className="text-[#6e7681]"
                />

                <span className="text-[10px] uppercase tracking-wide text-[#6e7681]">
                  AI Actions
                </span>
              </div>

              <div className="space-y-1">
                {actions.map(
                  (
                    action,
                  ) => {
                    const Icon =
                      action.icon;

                    const selected =
                      lastAction ===
                      action.id;

                    return (
                      <button
                        key={
                          action.id
                        }
                        type="button"
                        disabled={
                          isWorking
                        }
                        onClick={() =>
                          void executeAction(
                            action.id,
                          )
                        }
                        className={`group flex w-full items-start gap-3 rounded-md px-2 py-2 text-left transition-colors ${
                          selected
                            ? "bg-[#161b22]"
                            : "hover:bg-[#161b22]"
                        } disabled:cursor-wait disabled:opacity-60`}
                      >
                        <Icon
                          size={15}
                          className="mt-0.5 shrink-0 text-blue-400"
                        />

                        <span className="min-w-0">

                          <span className="block text-[11px] font-semibold text-[#d7dae0]">
                            {
                              action.title
                            }
                          </span>

                          <span className="mt-0.5 block text-[9px] leading-4 text-[#6e7681]">
                            {
                              action.description
                            }
                          </span>

                        </span>
                      </button>
                    );
                  },
                )}
              </div>

            </div>
          </div>

          {/* PROVIDER */}

          <div className="shrink-0 border-t border-[#252a33] px-3 pt-2">

            <span className="mb-1.5 block text-[9px] uppercase tracking-wide text-[#6e7681]">
              AI Provider
            </span>

            <div className="relative">

              <Settings2
                size={13}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#6e7681]"
              />

              <select
                value={provider}
                onChange={(
                  event,
                ) =>
                  setProvider(
                    event.target
                      .value,
                  )
                }
                className="h-9 w-full appearance-none rounded-md border border-[#30363d] bg-[#161b22] pl-8 pr-8 text-[12px] text-[#c9d1d9] outline-none transition-colors focus:border-blue-500"
              >
                <option>
                  Multi-LLM Orchestrator
                </option>

                <option>
                  GPT
                </option>

                <option>
                  Gemini
                </option>

                <option>
                  Llama
                </option>

                <option>
                  DeepSeek
                </option>
              </select>

              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6e7681]"
              />

            </div>
          </div>

          {/* INPUT */}

          <div className="shrink-0 p-3 pt-2">

            <div className="flex items-center gap-2">

              <div className="flex min-w-0 flex-1 items-center rounded-md border border-[#30363d] bg-[#0d1117] focus-within:border-blue-500">

                <Paperclip
                  size={14}
                  className="ml-2 shrink-0 text-[#6e7681]"
                />

                <input
                  type="text"
                  value={input}
                  onChange={(
                    event,
                  ) =>
                    setInput(
                      event.target
                        .value,
                    )
                  }
                  onKeyDown={
                    handleInputKeyDown
                  }
                  disabled={
                    isWorking
                  }
                  placeholder="Ask TestForge AI..."
                  className="h-9 min-w-0 flex-1 bg-transparent px-2 text-[11px] text-[#c9d1d9] outline-none placeholder:text-[#484f58]"
                />

              </div>

              <button
                type="button"
                disabled={
                  !input.trim() ||
                  isWorking
                }
                onClick={() =>
                  void handleSendMessage()
                }
                title="Send message"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isWorking ? (
                  <Loader2
                    size={15}
                    className="animate-spin"
                  />
                ) : (
                  <Send
                    size={15}
                  />
                )}
              </button>

            </div>
          </div>
        </>
      )}

    </aside>
  );
}

/* ==========================================================================
   CHAT VIEW
   ========================================================================== */

function ChatView({
  messages,
  isWorking,
  messagesEndRef,
}: {
  messages: ChatMessage[];
  isWorking: boolean;
  messagesEndRef: React.RefObject<
    HTMLDivElement | null
  >;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">

        {messages.map(
          (message) => (
            <div
              key={
                message.id
              }
              className={`mb-3 flex ${
                message.role ===
                "user"
                  ? "justify-end"
                  : "justify-start"
              }`}
            >

              {message.role ===
                "assistant" && (
                <div className="mr-2 flex h-6 w-6 shrink-0 items-center justify-center rounded bg-blue-500/10">
                  <Bot
                    size={13}
                    className="text-blue-400"
                  />
                </div>
              )}

              <div
                className={`max-w-[88%] whitespace-pre-wrap rounded-lg px-3 py-2 text-[10px] leading-5 ${
                  message.role ===
                  "user"
                    ? "bg-blue-600 text-white"
                    : "border border-[#30363d] bg-[#161b22] text-[#9da7b3]"
                }`}
              >
                {
                  message.content
                }
              </div>

            </div>
          ),
        )}

        {isWorking && (
          <div className="flex items-center gap-2 text-[10px] text-[#6e7681]">

            <Loader2
              size={12}
              className="animate-spin"
            />

            TestForge AI is analyzing...

          </div>
        )}

        <div
          ref={
            messagesEndRef
          }
        />

      </div>

      {messages.length ===
        1 && (
        <div className="mx-3 mb-3 rounded-lg border border-[#30363d] bg-[#161b22] p-3">

          <div className="mb-2 flex items-center gap-2">

            <Sparkles
              size={14}
              className="text-blue-400"
            />

            <span className="text-[11px] font-semibold text-[#d7dae0]">
              TestForge Assistant
            </span>

          </div>

          <p className="text-[10px] leading-5 text-[#8b949e]">
            Connect a repository
            and TestForge AI can
            generate tests, analyze
            failures, create
            automation, and perform
            repository-aware
            reasoning.
          </p>

        </div>
      )}

    </div>
  );
}

/* ==========================================================================
   CODE VIEW
   ========================================================================== */

function CodeView({
  onExplainCode,
}: {
  onExplainCode?: () => void;
}) {
  return (
    <div className="h-full overflow-y-auto p-3">

      <SectionTitle
        icon={
          <Code2 size={14} />
        }
        title="AI CODE ASSISTANT"
      />

      <InfoCard
        title="Repository-aware coding"
        description="Select a file in the editor and ask TestForge AI to explain, review, refactor, or improve the code."
      />

      <ActionCard
        icon={
          <Sparkles
            size={14}
          />
        }
        title="Explain Code"
        description="Understand the selected code."
        onClick={onExplainCode}
      />

      <ActionCard
        icon={
          <Wrench size={14} />
        }
        title="Refactor Code"
        description="Suggest cleaner implementation."
      />

      <ActionCard
        icon={
          <Bug size={14} />
        }
        title="Find Potential Bugs"
        description="Identify suspicious code paths."
      />

      <ActionCard
        icon={
          <Zap size={14} />
        }
        title="Optimize"
        description="Suggest performance improvements."
      />

    </div>
  );
}

/* ==========================================================================
   TESTS VIEW
   ========================================================================== */

function TestsView({
  onRunAction,
  generatedTests,
  generationCount,
  onGenerationCountChange,
  scenarioTypeSelection,
  onScenarioTypeSelectionChange,
  hasGeneratedScenarios,
  isWorking,
  error,
  frameworkSelection,
  onFrameworkSelectionChange,
  frameworkRecommendation,
  isRecommendingFramework,
  frameworkRecommendationError,
  onRecommendFramework,
  isGeneratingCode,
  generatedCode,
  savedGeneratedCodeFile,
  codeGenerationError,
  isSavingGeneratedCode,
  codeSaveError,
  onGenerateExecutableTests,
  onSaveGeneratedCode,
}: {
  onRunAction: (
    action: AIAction,
    testTypes?: TestType[],
  ) => Promise<void>;
  generatedTests: GeneratedTestCase[];
  generationCount: number;
  onGenerationCountChange: (value: number) => void;
  scenarioTypeSelection: ScenarioTypeSelection;
  onScenarioTypeSelectionChange: (
    value: ScenarioTypeSelection,
  ) => void;
  hasGeneratedScenarios: boolean;
  isWorking: boolean;
  error: string | null;
  frameworkSelection: TestingFramework | "";
  onFrameworkSelectionChange: (
    value: TestingFramework | "",
  ) => void;
  frameworkRecommendation: RepositoryAnalyzeResponse | null;
  isRecommendingFramework: boolean;
  frameworkRecommendationError: string | null;
  onRecommendFramework: () => void;
  isGeneratingCode: boolean;
  generatedCode: GeneratedTestCode | null;
  savedGeneratedCodeFile: string | null;
  codeGenerationError: string | null;
  isSavingGeneratedCode: boolean;
  codeSaveError: string | null;
  onGenerateExecutableTests: () => void;
  onSaveGeneratedCode: () => void;
}) {
  return (
    <div className="h-full overflow-y-auto p-3">
      <SectionTitle
        icon={<TestTube2 size={14} />}
        title="AI TESTING"
      />

      <InfoCard
        title="Repository-aware Test Generation"
        description="Generate functional, integration, API, regression, boundary, negative, exception, and edge-case scenarios from the indexed repository context."
      />

      <div className="mb-3 rounded-md border border-[#30363d] bg-[#161b22] p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
            Test Cases
          </span>
          <div className="flex items-center gap-2">
            <label className="text-[9px] text-[#6e7681]">
              Scenario type
              <select
                aria-label="Scenario type"
                value={scenarioTypeSelection}
                onChange={(event) => {
                  const value = event.target.value;
                  if (
                    value === "all" ||
                    value === "functional" ||
                    value === "integration" ||
                    value === "api" ||
                    value === "regression" ||
                    value === "boundary" ||
                    value === "negative" ||
                    value === "exception" ||
                    value === "edge_case"
                  ) {
                    onScenarioTypeSelectionChange(value);
                  }
                }}
                disabled={isWorking}
                className="ml-1 h-7 rounded border border-[#30363d] bg-[#0d1117] px-2 text-[10px] text-[#c9d1d9] outline-none focus:border-blue-500"
              >
                <option value="all">All categories</option>
                <option value="functional">Functional</option>
                <option value="integration">Integration</option>
                <option value="api">API</option>
                <option value="regression">Regression</option>
                <option value="boundary">Boundary</option>
                <option value="negative">Negative</option>
                <option value="exception">Exception</option>
                <option value="edge_case">Edge Case</option>
              </select>
            </label>
            <label className="text-[9px] text-[#6e7681]">
              Count
              <select
                aria-label="Test case count"
                value={generationCount}
                onChange={(event) =>
                  onGenerationCountChange(Number(event.target.value))
                }
                disabled={isWorking}
                className="ml-1 h-7 rounded border border-[#30363d] bg-[#0d1117] px-2 text-[10px] text-[#c9d1d9] outline-none focus:border-blue-500"
              >
                {[1, 3, 5, 8, 10, 15, 50].map((count) => (
                  <option key={count} value={count}>
                    {count}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <button
          type="button"
          disabled={isWorking}
          onClick={() => void onRunAction("generate-tests")}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-[10px] font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-wait disabled:opacity-60"
        >
          {isWorking ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Sparkles size={13} />
          )}
          {isWorking ? "Generating scenarios..." : "Generate Test Cases"}
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/5 p-3">
          <div className="flex items-center gap-2 text-red-300">
            <Bug size={13} />
            <span className="text-[10px] font-semibold">Generation failed</span>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-[9px] leading-4 text-[#9da7b3]">
            {error}
          </p>
        </div>
      )}

      <div className="mb-3 rounded-md border border-[#30363d] bg-[#161b22] p-3">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
          Test Framework
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[9px] text-[#6e7681]">
            Framework
            <select
              aria-label="Test framework"
              value={frameworkSelection}
              onChange={(event) => {
                const value = event.target.value;
                if (
                  value === "" ||
                  value === "pytest" ||
                  value === "playwright" ||
                  value === "selenium"
                ) {
                  onFrameworkSelectionChange(value);
                }
              }}
              disabled={
                isGeneratingCode ||
                isSavingGeneratedCode ||
                isRecommendingFramework
              }
              className="ml-1 h-7 rounded border border-[#30363d] bg-[#0d1117] px-2 text-[10px] text-[#c9d1d9] outline-none focus:border-blue-500"
            >
              <option value="">Choose manually or recommend</option>
              <option
                value="pytest"
                disabled={
                  !frameworkRecommendation?.supported_test_frameworks?.includes(
                    "pytest",
                  )
                }
              >
                Pytest
              </option>
              <option
                value="playwright"
                disabled={
                  !frameworkRecommendation?.supported_test_frameworks?.includes(
                    "playwright",
                  )
                }
              >
                Playwright
              </option>
              <option
                value="selenium"
                disabled={
                  !frameworkRecommendation?.supported_test_frameworks?.includes(
                    "selenium",
                  )
                }
              >
                Selenium
              </option>
            </select>
          </label>
          <button
            type="button"
            disabled={isWorking || isRecommendingFramework}
            onClick={onRecommendFramework}
            className="rounded border border-[#30363d] px-2 py-1 text-[9px] text-[#c9d1d9] hover:bg-[#21262d] disabled:cursor-wait disabled:opacity-60"
          >
            {isRecommendingFramework
              ? "Analyzing repository..."
              : "Recommend Framework"}
          </button>
        </div>
        {frameworkRecommendation?.recommended_test_framework && (
          <div className="mt-2 text-[9px] leading-4 text-[#9da7b3]">
            <p>
              Recommended:{" "}
              <span className="font-semibold text-blue-300">
                {frameworkRecommendation.recommended_test_framework}
              </span>
            </p>
            {frameworkRecommendation.framework_recommendation_evidence?.map(
              (evidence) => (
                <p key={evidence} className="break-words">
                  Evidence: {evidence}
                </p>
              ),
            )}
          </div>
        )}
        {frameworkRecommendation?.supported_test_frameworks &&
          frameworkRecommendation.supported_test_frameworks.length > 0 && (
            <p className="mt-2 text-[9px] leading-4 text-[#9da7b3]">
              Detected support:{" "}
              {frameworkRecommendation.supported_test_frameworks.join(", ")}
              {" · "}
              Languages:{" "}
              {frameworkRecommendation.supported_test_languages?.join(", ") ||
                "none detected"}
            </p>
          )}
        {frameworkRecommendationError && (
          <p role="status" className="mt-2 text-[9px] leading-4 text-amber-300">
            {frameworkRecommendationError}
          </p>
        )}
        {codeGenerationError && (
          <p
            role={generatedCode ? "status" : "alert"}
            className={`mt-2 whitespace-pre-wrap text-[9px] leading-4 ${
              generatedCode ? "text-amber-300" : "text-red-300"
            }`}
          >
            {generatedCode
              ? `Context note: ${codeGenerationError}`
              : codeGenerationError}
          </p>
        )}
        {codeSaveError && (
          <p role="alert" className="mt-2 whitespace-pre-wrap text-[9px] leading-4 text-red-300">
            {codeSaveError}
          </p>
        )}
        {generatedCode && (
          <p role="status" className="mt-2 break-words text-[9px] leading-4 text-emerald-300">
            Validated code ready to save: {generatedCode.file_path}
          </p>
        )}
        {savedGeneratedCodeFile && (
          <p role="status" className="mt-2 break-words text-[9px] leading-4 text-emerald-300">
            Saved and opened in the editor: {savedGeneratedCodeFile}
          </p>
        )}
        {generatedTests.length > 0 && (
          <button
            type="button"
            disabled={
              isWorking ||
              isGeneratingCode ||
              isSavingGeneratedCode ||
              !frameworkSelection
            }
            onClick={onGenerateExecutableTests}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-md border border-blue-500/40 px-3 py-2 text-[10px] font-medium text-blue-200 hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isGeneratingCode
              ? "Generating executable tests..."
              : "Generate Executable Tests"}
          </button>
        )}
        {generatedCode && !savedGeneratedCodeFile && (
          <button
            type="button"
            disabled={isSavingGeneratedCode}
            onClick={onSaveGeneratedCode}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-md border border-emerald-500/40 px-3 py-2 text-[10px] font-medium text-emerald-200 hover:bg-emerald-500/10 disabled:cursor-wait disabled:opacity-50"
          >
            {isSavingGeneratedCode
              ? "Saving generated test..."
              : "Save Generated Test"}
          </button>
        )}
      </div>

      {generatedTests.length === 0 && !hasGeneratedScenarios ? (
        <>
          <ActionCard
            icon={<TestTube2 size={14} />}
            title="Functional Tests"
            description="Generate functional scenarios."
          />
          <ActionCard
            icon={<Play size={14} />}
            title="Integration Tests"
            description="Generate integration scenarios."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("integration");
              void onRunAction("generate-tests", ["integration"]);
            }}
          />
          <ActionCard
            icon={<Zap size={14} />}
            title="API Test Scenarios"
            description="Generate API scenarios from evidenced routes and contracts."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("api");
              void onRunAction("generate-tests", ["api"]);
            }}
          />
          <ActionCard
            icon={<Bug size={14} />}
            title="Negative Tests"
            description="Generate negative scenarios."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("negative");
              void onRunAction("generate-tests", ["negative"]);
            }}
          />
          <ActionCard
            icon={<CheckCircle2 size={14} />}
            title="Boundary Tests"
            description="Test evidenced limits and thresholds."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("boundary");
              void onRunAction("generate-tests", ["boundary"]);
            }}
          />
          <ActionCard
            icon={<CheckCircle2 size={14} />}
            title="Regression Tests"
            description="Verify evidenced existing behavior remains reliable."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("regression");
              void onRunAction("generate-tests", ["regression"]);
            }}
          />
          <ActionCard
            icon={<Bug size={14} />}
            title="Exception Tests"
            description="Verify evidenced exception handling and propagation."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("exception");
              void onRunAction("generate-tests", ["exception"]);
            }}
          />
          <ActionCard
            icon={<Zap size={14} />}
            title="Edge-Case Tests"
            description="Exercise evidenced unusual states and combinations."
            disabled={isWorking}
            onClick={() => {
              onScenarioTypeSelectionChange("edge_case");
              void onRunAction("generate-tests", ["edge_case"]);
            }}
          />
        </>
      ) : (
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
              Generated Scenarios
            </span>
            <span className="text-[9px] text-[#6e7681]">
              {generatedTests.length} cases
            </span>
          </div>

          {generatedTests.length === 0 ? (
            <p
              role="status"
              className="rounded-md border border-[#30363d] bg-[#11161d] p-3 text-[9px] leading-4 text-[#8b949e]"
            >
              No scenarios were returned for this request.
            </p>
          ) : (
            <div className="space-y-2">
              {generatedTests.map((testCase, index) => (
                <GeneratedTestCard
                  key={testCase.id || `${testCase.title}-${index}`}
                  testCase={testCase}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GeneratedTestCard({
  testCase,
}: {
  testCase: GeneratedTestCase;
}) {
  return (
    <div className="rounded-md border border-[#30363d] bg-[#11161d] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words text-[10px] font-semibold leading-4 text-[#d7dae0]">
            {testCase.title || "Untitled scenario"}
          </p>
          <p className="mt-1 whitespace-pre-wrap break-words text-[9px] leading-4 text-[#8b949e]">
            {testCase.description || "No description provided."}
          </p>
        </div>
        <span className="shrink-0 rounded border border-blue-500/20 bg-blue-500/5 px-1.5 py-1 text-[8px] uppercase text-blue-300">
          {testCase.priority || "medium"}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded border border-[#30363d] bg-[#0d1117] px-1.5 py-1 text-[8px] text-[#8b949e]">
          {testCase.test_type}
        </span>
        {testCase.target_file && (
          <span className="max-w-full truncate rounded border border-[#30363d] bg-[#0d1117] px-1.5 py-1 text-[8px] text-[#6e7681]">
            {testCase.target_file}
          </span>
        )}
        {testCase.target_function && (
          <span className="max-w-full truncate rounded border border-[#30363d] bg-[#0d1117] px-1.5 py-1 text-[8px] text-[#6e7681]">
            {testCase.target_function}()
          </span>
        )}
      </div>

      {testCase.preconditions?.length > 0 && (
        <div className="mt-2">
          <p className="mb-1 text-[8px] font-semibold uppercase tracking-wide text-[#6e7681]">
            Preconditions
          </p>
          <ul className="space-y-1">
            {testCase.preconditions.map((item, index) => (
              <li key={`${item}-${index}`} className="break-words text-[9px] leading-4 text-[#9da7b3]">
                • {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {testCase.steps?.length > 0 && (
        <div className="mt-2">
          <p className="mb-1 text-[8px] font-semibold uppercase tracking-wide text-[#6e7681]">
            Steps
          </p>
          <ol className="space-y-1">
            {testCase.steps.map((step, index) => (
              <li key={`${step}-${index}`} className="break-words text-[9px] leading-4 text-[#9da7b3]">
                <span className="mr-1 text-blue-400">{index + 1}.</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="mt-2 rounded border border-emerald-500/10 bg-emerald-500/5 p-2">
        <p className="mb-1 text-[8px] font-semibold uppercase tracking-wide text-emerald-400">
          Expected Result
        </p>
        <p className="whitespace-pre-wrap break-words text-[9px] leading-4 text-[#9da7b3]">
          {testCase.expected_result || "No expected result provided."}
        </p>
      </div>
    </div>
  );
}

/* ==========================================================================
   INSIGHTS VIEW
   ========================================================================== */

function InsightsView({
  analysis,
  provider,
  model,
  error,
  isWorking,
  onAnalyze,
}: {
  analysis: RepositoryAnalysis | null;
  provider: string | null;
  model: string | null;
  error: string | null;
  isWorking: boolean;
  onAnalyze: () => void;
}) {
  if (isWorking && !analysis) {
    return (
      <div className="h-full overflow-y-auto p-3">

        <SectionTitle
          icon={
            <Activity
              size={14}
            />
          }
          title="AI INSIGHTS"
        />

        <div className="rounded-md border border-[#30363d] bg-[#161b22] p-4">

          <div className="flex items-center gap-2">

            <Loader2
              size={15}
              className="animate-spin text-blue-400"
            />

            <span className="text-[11px] font-semibold text-[#d7dae0]">
              Analyzing repository...
            </span>

          </div>

          <p className="mt-2 text-[10px] leading-5 text-[#6e7681]">
            TestForge is retrieving repository
            context and building structured
            testing insights.
          </p>

        </div>

      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full overflow-y-auto p-3">

        <SectionTitle
          icon={
            <Activity
              size={14}
            />
          }
          title="AI INSIGHTS"
        />

        <div className="rounded-md border border-red-500/30 bg-red-500/5 p-3">

          <div className="flex items-center gap-2">

            <Bug
              size={14}
              className="text-red-400"
            />

            <span className="text-[11px] font-semibold text-red-300">
              Analysis failed
            </span>

          </div>

          <p className="mt-2 whitespace-pre-wrap text-[10px] leading-5 text-[#9da7b3]">
            {error}
          </p>

          <button
            type="button"
            onClick={onAnalyze}
            disabled={isWorking}
            className="mt-3 flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-[10px] font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            <Activity
              size={12}
            />
            Retry Analysis
          </button>

        </div>

      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="h-full overflow-y-auto p-3">

        <SectionTitle
          icon={
            <Activity
              size={14}
            />
          }
          title="AI INSIGHTS"
        />

        <div className="rounded-md border border-[#30363d] bg-[#161b22] p-4">

          <div className="flex items-center gap-2">

            <Sparkles
              size={14}
              className="text-blue-400"
            />

            <span className="text-[11px] font-semibold text-[#d7dae0]">
              Repository Intelligence
            </span>

          </div>

          <p className="mt-2 text-[10px] leading-5 text-[#8b949e]">
            Run Analyze Repository to build
            structured repository-aware
            testing insights.
          </p>

          <button
            type="button"
            onClick={onAnalyze}
            disabled={isWorking}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-[10px] font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
          >
            <Sparkles
              size={13}
            />

            Analyze Repository
          </button>

        </div>

      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3">

      <SectionTitle
        icon={
          <Activity
            size={14}
          />
        }
        title="AI INSIGHTS"
      />

      {/* Provider */}

      <div className="mb-3 flex items-center justify-between rounded-md border border-[#252a33] bg-[#11161d] px-3 py-2">

        <span className="text-[9px] uppercase tracking-wide text-[#6e7681]">
          AI Engine
        </span>

        <span className="text-right text-[9px] text-[#8b949e]">
          {provider || "Unknown"}
          {model
            ? ` · ${model}`
            : ""}
        </span>

      </div>

      {/* Architecture */}

      <InsightSection
        title="Architecture"
        icon={
          <Code2 size={13} />
        }
        emptyText="No architecture information detected."
      >
        <p className="text-[10px] leading-5 text-[#9da7b3]">
          {analysis.architecture ||
            "No architecture information detected."}
        </p>
      </InsightSection>

      {/* Technologies */}

      <InsightSection
        title="Technologies"
        icon={
          <Zap size={13} />
        }
        emptyText="No technologies detected."
      >
        <TagList
          items={
            analysis.technologies
          }
          emptyText="No technologies detected."
        />
      </InsightSection>

      {/* Dependencies */}

      <InsightSection
        title="Dependencies"
        icon={
          <Wrench size={13} />
        }
        emptyText="No dependencies detected."
      >
        <TagList
          items={
            analysis.dependencies
          }
          emptyText="No dependencies detected."
        />
      </InsightSection>

      {/* Important Modules */}

      <InsightSection
        title="Important Modules"
        icon={
          <FileCode2
            size={13}
          />
        }
        emptyText="No important modules detected."
      >
        <ItemList
          items={
            analysis.important_modules
          }
          emptyText="No important modules detected."
        />
      </InsightSection>

      {/* APIs */}

      <InsightSection
        title="APIs"
        icon={
          <Activity
            size={13}
          />
        }
        emptyText="No API specifications detected."
      >
        <ItemList
          items={analysis.apis}
          emptyText="No API specifications detected."
        />
      </InsightSection>

      {/* Configurations */}

      <InsightSection
        title="Configurations"
        icon={
          <Settings2
            size={13}
          />
        }
        emptyText="No configuration files detected."
      >
        <ItemList
          items={
            analysis.configurations
          }
          emptyText="No configuration files detected."
        />
      </InsightSection>

      {/* Existing Tests */}

      <InsightSection
        title="Existing Tests"
        icon={
          <TestTube2
            size={13}
          />
        }
        emptyText="No existing tests detected."
      >
        <ItemList
          items={
            analysis.existing_tests
          }
          emptyText="No existing tests detected."
        />
      </InsightSection>

      {/* Automation */}

      <InsightSection
        title="Automation Assets"
        icon={
          <Play size={13} />
        }
        emptyText="No automation assets detected."
      >
        <ItemList
          items={
            analysis.automation_assets
          }
          emptyText="No automation assets detected."
        />
      </InsightSection>

      {/* Testing Areas */}

      <InsightSection
        title="Recommended Testing Areas"
        icon={
          <Lightbulb
            size={13}
          />
        }
        emptyText="No testing areas were derived."
      >
        <ItemList
          items={
            analysis.testing_areas
          }
          emptyText="No testing areas were derived."
        />
      </InsightSection>

      {/* Refresh */}

      <button
        type="button"
        onClick={onAnalyze}
        disabled={isWorking}
        className="mt-1 flex w-full items-center justify-center gap-2 rounded-md border border-[#30363d] bg-[#161b22] px-3 py-2 text-[10px] font-medium text-[#c9d1d9] transition-colors hover:border-blue-500 hover:text-white disabled:opacity-50"
      >
        {isWorking ? (
          <Loader2
            size={12}
            className="animate-spin"
          />
        ) : (
          <Activity
            size={12}
          />
        )}

        Refresh Repository Analysis
      </button>

    </div>
  );
}

/* ==========================================================================
   INSIGHT COMPONENTS
   ========================================================================== */

function InsightSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  emptyText: string;
}) {
  return (
    <div className="mb-2 rounded-md border border-[#252a33] bg-[#11161d] p-3">

      <div className="mb-2 flex items-center gap-2">

        <span className="text-blue-400">
          {icon}
        </span>

        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
          {title}
        </span>

      </div>

      {children}

    </div>
  );
}

function TagList({
  items,
  emptyText,
}: {
  items: string[];
  emptyText: string;
}) {
  if (!items.length) {
    return (
      <p className="text-[10px] text-[#6e7681]">
        {emptyText}
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(
        (item) => (
          <span
            key={item}
            className="rounded border border-blue-500/20 bg-blue-500/5 px-2 py-1 text-[9px] text-[#9da7b3]"
          >
            {item}
          </span>
        ),
      )}
    </div>
  );
}

function ItemList({
  items,
  emptyText,
}: {
  items: string[];
  emptyText: string;
}) {
  if (!items.length) {
    return (
      <p className="text-[10px] text-[#6e7681]">
        {emptyText}
      </p>
    );
  }

  return (
    <div className="space-y-1.5">
      {items.map(
        (item) => (
          <div
            key={item}
            className="rounded border border-[#252a33] bg-[#0d1117] px-2 py-1.5 text-[9px] leading-4 text-[#9da7b3]"
          >
            {item}
          </div>
        ),
      )}
    </div>
  );
}

/* ==========================================================================
   UI COMPONENTS
   ========================================================================== */

function AITabButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`relative flex flex-1 items-center justify-center gap-1.5 text-[11px] transition-colors ${
        active
          ? "text-white"
          : "text-[#6e7681] hover:text-[#c9d1d9]"
      }`}
    >
      {icon}

      {label}

      {active && (
        <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-blue-500" />
      )}
    </button>
  );
}

function SectionTitle({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">

      <span className="text-blue-400">
        {icon}
      </span>

      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
        {title}
      </span>

    </div>
  );
}

function InfoCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-3 rounded-md border border-[#30363d] bg-[#161b22] p-3">

      <p className="text-[11px] font-semibold text-[#d7dae0]">
        {title}
      </p>

      <p className="mt-1 text-[10px] leading-5 text-[#6e7681]">
        {description}
      </p>

    </div>
  );
}

function ActionCard({
  icon,
  title,
  description,
  onClick,
  disabled = false,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="mb-1.5 flex w-full items-start gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-[#161b22] disabled:cursor-wait disabled:opacity-60"
    >

      <span className="mt-0.5 text-blue-400">
        {icon}
      </span>

      <span>

        <span className="block text-[10px] font-semibold text-[#c9d1d9]">
          {title}
        </span>

        <span className="mt-0.5 block text-[9px] leading-4 text-[#6e7681]">
          {description}
        </span>

      </span>

    </button>
  );
}