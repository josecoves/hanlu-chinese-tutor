"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { loadOfflineProgress, saveOfflineProgress } from "./offline-progress";
import { loadWritingDraft, saveWritingDraft } from "./offline-writing";

type Word = {
  id: number;
  hanzi: string;
  pinyin: string;
  meaning: string;
  hsk: number;
  hskLevels: number[];
  topics: string[];
  measureWord: string;
  audio: string;
};
type Sentence = {
  zh: string;
  pinyin: string;
  en: string;
  audio: string;
  words: Array<Pick<Word, "id" | "hanzi" | "pinyin" | "meaning" | "hsk">>;
};
type Story = {
  id: number;
  titleZh: string;
  titleEn: string;
  hskLevel: number;
  sentences: Sentence[];
};
type Grammar = {
  id: number;
  level: number;
  titleZh: string;
  titleEn: string;
  pattern: string;
  explanation: string;
  recommendedEarly: boolean;
  examples: Array<{ zh: string; pinyin: string; en: string; audio: string }>;
  practiceExamples: Array<{ zh: string; pinyin: string; en: string; audio: string; source: string }>;
};
type Content = { words: Word[]; stories: Story[]; grammar: Grammar[] };
type StoryProgress = {
  sentenceIndex: number;
  status?: "new" | "reading" | "finished";
  completedAt?: string;
  completedSentences?: number[];
  hardWords?: Record<string, number[]>;
};
type VocabularyProgress = {
  listeningScore?: number;
  readingScore?: number;
  practices: number;
  lastReviewTs?: string;
  needsPractice?: boolean;
  known?: boolean;
};
type GrammarStatus = "new" | "practicing" | "learned";
type CloudProgress = {
  version: 2;
  declaredHskBand: number;
  stories: Record<string, StoryProgress>;
  grammar: Record<string, GrammarStatus>;
  vocabulary: Record<string, VocabularyProgress>;
};
type SyncState = "loading" | "saved" | "offline";
type WritingMode = "prompt" | "message" | "translation" | "guided";
type ReviewSection = { status: string; feedback: string };
type WritingFeedback = {
  verdict: "clear" | "needs_revision";
  summary: string;
  taskCompletion: ReviewSection;
  grammarWordOrder: ReviewSection;
  vocabularyNaturalness: ReviewSection;
  charactersTyping: ReviewSection;
  placeholders: Array<{
    english: string;
    chinese: string;
    pinyin: string;
    hskLevel: string;
    note: string;
  }>;
  correctedChinese: string;
  changes: Array<{ original: string; replacement: string; reason: string }>;
  revisionPrompt: string;
};
type Tab =
  | "Today"
  | "Vocabulary"
  | "Topics"
  | "Stories"
  | "Comprehension"
  | "Writing"
  | "Grammar"
  | "Progress"
  | "Settings";

const tabs: Tab[] = [
  "Today",
  "Vocabulary",
  "Topics",
  "Stories",
  "Comprehension",
  "Writing",
  "Grammar",
  "Progress",
  "Settings",
];

function speak(text: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 0.82;
  window.speechSynthesis.speak(utterance);
}

function playAudio(text: string, audio?: string) {
  if (!audio) {
    speak(text);
    return;
  }
  const player = new Audio(`/audio/${audio}`);
  player.addEventListener("error", () => speak(text), { once: true });
  void player.play().catch(() => speak(text));
}

export function HanluApp({ content }: { content: Content }) {
  const [tab, setTab] = useState<Tab>("Today");
  const [query, setQuery] = useState("");
  const [hsk, setHsk] = useState(0);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [practiceFilter, setPracticeFilter] = useState("all");
  const [wordSort, setWordSort] = useState("hsk");
  const [storyId, setStoryId] = useState<number | null>(null);
  const [sentenceIndex, setSentenceIndex] = useState(0);
  const [showPinyin, setShowPinyin] = useState(true);
  const [showTranslation, setShowTranslation] = useState(false);
  const [grammarId, setGrammarId] = useState<number | null>(null);
  const [progress, setProgress] = useState<CloudProgress>({
    version: 2,
    declaredHskBand: 0,
    stories: {},
    grammar: {},
    vocabulary: {},
  });
  const [syncState, setSyncState] = useState<SyncState>("loading");
  const [progressLoaded, setProgressLoaded] = useState(false);
  const [canSyncProgress, setCanSyncProgress] = useState(false);
  const [syncAttempt, setSyncAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/progress", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Progress is unavailable");
        return response.json() as Promise<{ progress: CloudProgress }>;
      })
      .then(({ progress: remoteProgress }) => {
        if (cancelled) return;
        if (remoteProgress?.version === 2) {
          setProgress(remoteProgress);
          void saveOfflineProgress(remoteProgress);
        }
        setCanSyncProgress(true);
        setSyncState("saved");
      })
      .catch(async () => {
        try {
          const cachedProgress = await loadOfflineProgress<CloudProgress>();
          if (!cancelled && cachedProgress?.version === 2) {
            setProgress(cachedProgress);
            setCanSyncProgress(true);
          }
        } catch {
          // Cloud sync can still be retried without an offline cache.
        }
        if (!cancelled) setSyncState("offline");
      })
      .finally(() => {
        if (!cancelled) setProgressLoaded(true);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!progressLoaded || !canSyncProgress) return;
    void saveOfflineProgress(progress).catch(() => undefined);
    if (!navigator.onLine) {
      const timeout = window.setTimeout(() => setSyncState("offline"), 0);
      return () => window.clearTimeout(timeout);
    }
    const timeout = window.setTimeout(() => {
      setSyncState("loading");
      void fetch("/api/progress", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(progress),
      })
        .then((response) => {
          if (!response.ok) throw new Error("Progress save failed");
          setSyncState("saved");
        })
        .catch(() => setSyncState("offline"));
    }, 500);
    return () => window.clearTimeout(timeout);
  }, [canSyncProgress, progress, progressLoaded, syncAttempt]);

  useEffect(() => {
    const retryWhenOnline = () => setSyncAttempt((attempt) => attempt + 1);
    window.addEventListener("online", retryWhenOnline);
    return () => window.removeEventListener("online", retryWhenOnline);
  }, []);

  const topics = useMemo(() => {
    const grouped = new Map<string, { one: number; two: number }>();
    for (const word of content.words) {
      for (const topic of word.topics) {
        const value = grouped.get(topic) ?? { one: 0, two: 0 };
        if (word.hsk === 1) value.one += 1;
        if (word.hsk === 2) value.two += 1;
        grouped.set(topic, value);
      }
    }
    return [...grouped.entries()]
      .map(([name, counts]) => ({ name, ...counts }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [content.words]);

  const filteredWords = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const result = content.words
      .filter((word) => !hsk || word.hsk === hsk)
      .filter((word) => !selectedTopics.length || selectedTopics.some((topic) => word.topics.includes(topic)))
      .filter(
        (word) =>
          !needle ||
          word.hanzi.includes(needle) ||
          word.pinyin.toLowerCase().includes(needle) ||
          word.meaning.toLowerCase().includes(needle) ||
          word.topics.some((topic) => topic.toLowerCase().includes(needle)),
      )
      .filter((word) => {
        const state = progress.vocabulary[String(word.id)];
        if (practiceFilter === "unpracticed") return !state?.practices;
        if (practiceFilter === "practiced") return Boolean(state?.practices);
        if (practiceFilter === "review") return Boolean(state?.needsPractice);
        return true;
      });
    result.sort((a, b) => {
      const aState = progress.vocabulary[String(a.id)];
      const bState = progress.vocabulary[String(b.id)];
      if (wordSort === "hanzi") return a.hanzi.localeCompare(b.hanzi, "zh");
      if (wordSort === "practiced") return (bState?.practices ?? 0) - (aState?.practices ?? 0) || a.hsk - b.hsk;
      if (wordSort === "last") return (bState?.lastReviewTs ?? "").localeCompare(aState?.lastReviewTs ?? "");
      return a.hsk - b.hsk || a.id - b.id;
    });
    return result.slice(0, 1_500);
  }, [content.words, hsk, practiceFilter, progress.vocabulary, query, selectedTopics, wordSort]);

  const openTopic = (name: string, level: number) => {
    setQuery("");
    setSelectedTopics([name]);
    setHsk(level);
    setTab("Vocabulary");
  };

  const openStory = (id: number) => {
    setStoryId(id);
    setSentenceIndex(progress.stories[String(id)]?.sentenceIndex ?? 0);
    setShowPinyin(true);
    setShowTranslation(false);
  };

  const updateVocabularyProgress = (id: number, update: (current: VocabularyProgress) => VocabularyProgress) => {
    setCanSyncProgress(true);
    setProgress((current) => ({
      ...current,
      vocabulary: {
        ...current.vocabulary,
        [id]: update(current.vocabulary[String(id)] ?? { practices: 0 }),
      },
    }));
  };

  const completeStorySentence = (story: Story, index: number, hardWordIds: number[]) => {
    setCanSyncProgress(true);
    setProgress((current) => {
      const existing = current.stories[String(story.id)] ?? { sentenceIndex: 0 };
      const completed = new Set(existing.completedSentences ?? []);
      completed.add(index);
      const finished = completed.size >= story.sentences.length;
      const hardWords = { ...(existing.hardWords ?? {}), [String(index)]: hardWordIds };
      const vocabulary = { ...current.vocabulary };
      for (const word of story.sentences[index].words) {
        const wordState = vocabulary[String(word.id)] ?? { practices: 0 };
        if (hardWordIds.includes(word.id)) {
          vocabulary[String(word.id)] = { ...wordState, needsPractice: true, known: false };
        }
      }
      return {
        ...current,
        vocabulary,
        stories: {
          ...current.stories,
          [story.id]: {
            ...existing,
            sentenceIndex: finished ? index : Math.min(story.sentences.length - 1, index + 1),
            status: finished ? "finished" : "reading",
            completedSentences: [...completed].sort((a, b) => a - b),
            hardWords,
            ...(finished ? { completedAt: new Date().toISOString() } : {}),
          },
        },
      };
    });
  };

  const updateGrammarStatus = (id: number, status: GrammarStatus) => {
    setCanSyncProgress(true);
    setProgress((current) => ({
      ...current,
      grammar: { ...current.grammar, [id]: status },
    }));
  };

  return (
    <div className="site-shell">
      <header className="site-header">
        <button className="brand" onClick={() => setTab("Today")}>
          <span>汉路</span>
          <small>HANLU · CHINESE TUTOR</small>
        </button>
        <nav aria-label="Main navigation">
          {tabs.map((item) => (
            <button
              key={item}
              className={tab === item ? "active" : ""}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </header>

      <main>
        {tab === "Today" && (
          <Today
            content={content}
            topics={topics}
            onTab={setTab}
            onStory={(id) => {
              setTab("Stories");
              openStory(id);
            }}
          />
        )}
        {tab === "Vocabulary" && (
          <Vocabulary
            words={filteredWords}
            allTopics={topics.map((topic) => topic.name)}
            query={query}
            setQuery={setQuery}
            hsk={hsk}
            setHsk={setHsk}
            selectedTopics={selectedTopics}
            setSelectedTopics={setSelectedTopics}
            practiceFilter={practiceFilter}
            setPracticeFilter={setPracticeFilter}
            sort={wordSort}
            setSort={setWordSort}
            progress={progress}
            updateProgress={updateVocabularyProgress}
          />
        )}
        {tab === "Topics" && (
          <Topics topics={topics} words={content.words} progress={progress} onOpen={openTopic} />
        )}
        {tab === "Stories" && (
          <Stories
            stories={content.stories}
            storyId={storyId}
            sentenceIndex={sentenceIndex}
            setSentenceIndex={setSentenceIndex}
            openStory={openStory}
            closeStory={() => setStoryId(null)}
            showPinyin={showPinyin}
            setShowPinyin={setShowPinyin}
            showTranslation={showTranslation}
            setShowTranslation={setShowTranslation}
            progress={progress.stories}
            vocabularyProgress={progress.vocabulary}
            onCompleteSentence={completeStorySentence}
            onStatus={(id, status) => {
              setCanSyncProgress(true);
              setProgress((current) => ({ ...current, stories: { ...current.stories, [id]: { ...(current.stories[String(id)] ?? { sentenceIndex: 0 }), status, ...(status === "finished" ? { completedAt: new Date().toISOString() } : {}) } } }));
            }}
          />
        )}
        {tab === "Comprehension" && <Comprehension />}
        {tab === "Writing" && <WritingStudio content={content} />}
        {tab === "Grammar" && (
          <GrammarLibrary
            lessons={content.grammar}
            selectedId={grammarId}
            setSelectedId={setGrammarId}
            statuses={progress.grammar}
            setStatus={updateGrammarStatus}
          />
        )}
        {tab === "Progress" && <Progress content={content} progress={progress} syncState={syncState} />}
        {tab === "Settings" && <Settings syncState={syncState} onImported={(imported) => { setProgress(imported); setCanSyncProgress(true); void saveOfflineProgress(imported); }} />}
      </main>

      <footer>
        <span>汉路 private hosted beta · {syncState === "saved" ? "progress synced" : syncState === "loading" ? "syncing progress" : "saved on this device · sync queued"}</span>
        <a
          href="https://github.com/josecoves/hanlu-chinese-tutor"
          target="_blank"
          rel="noreferrer"
        >
          Source on GitHub ↗
        </a>
      </footer>
    </div>
  );
}

function Today({
  content,
  topics,
  onTab,
  onStory,
}: {
  content: Content;
  topics: Array<{ name: string; one: number; two: number }>;
  onTab: (tab: Tab) => void;
  onStory: (id: number) => void;
}) {
  return (
    <>
      <section className="hero">
        <div>
          <span className="eyebrow">READ · NOTICE · REMEMBER</span>
          <h1>Chinese that lives in context.</h1>
          <p>
            Build a practical vocabulary through short stories, clear grammar,
            and level-aware study.
          </p>
          <div className="hero-actions">
            <button className="primary" onClick={() => onStory(content.stories[0].id)}>
              Read a story →
            </button>
            <button onClick={() => onTab("Vocabulary")}>Explore vocabulary</button>
          </div>
        </div>
        <aside>
          <span>今天的句子</span>
          <strong>每天读一点儿，中文就会越来越自然。</strong>
          <em>Měitiān dú yìdiǎnr, Zhōngwén jiù huì yuèláiyuè zìrán.</em>
          <p>Read a little every day, and Chinese becomes more natural.</p>
          <button onClick={() => speak("每天读一点儿，中文就会越来越自然。")}>
            A · Play audio
          </button>
        </aside>
      </section>
      <section className="stats" aria-label="Curriculum size">
        <div><strong>{content.words.length.toLocaleString()}</strong><span>HSK 1–2 words</span></div>
        <div><strong>{content.stories.length}</strong><span>graded stories</span></div>
        <div><strong>{content.grammar.length}</strong><span>grammar lessons</span></div>
        <div><strong>{topics.length}</strong><span>everyday topics</span></div>
      </section>
      <section className="section">
        <div className="section-heading">
          <div><span className="eyebrow">START SOMEWHERE USEFUL</span><h2>Choose your path</h2></div>
        </div>
        <div className="path-grid">
          <button onClick={() => onTab("Stories")}><b>01</b><strong>Read in context</strong><span>Stories with pinyin, translation, and audio.</span></button>
          <button onClick={() => onTab("Grammar")}><b>02</b><strong>Understand the pattern</strong><span>HSK-organized explanations and examples.</span></button>
          <button onClick={() => onTab("Writing")}><b>03</b><strong>Write something real</strong><span>Messages, short prompts, translations, and guided vocabulary practice.</span></button>
        </div>
      </section>
    </>
  );
}

const writingModes: Array<{
  id: WritingMode;
  label: string;
  description: string;
}> = [
  { id: "prompt", label: "Short response", description: "Answer a practical question in 2–5 sentences." },
  { id: "message", label: "Message reply", description: "Reply naturally to a text, invitation, or request." },
  { id: "translation", label: "Story translation", description: "Retell a short English scene in Chinese." },
  { id: "guided", label: "Target words", description: "Write freely while using selected vocabulary." },
];

const writingPrompts: Record<WritingMode, Record<number, string[]>> = {
  prompt: {
    1: [
      "Introduce yourself. Say where you live, what languages you speak, and one thing you like.",
      "Describe your normal morning in 2–4 sentences.",
      "What do you like to eat and drink? Say when or where you usually have it.",
      "Describe one person in your family and something you do together.",
    ],
    2: [
      "Describe a recent weekend: where you went, who was there, and how you felt.",
      "Explain how you are learning Chinese and what is still difficult.",
      "A friend will visit your city. Recommend a simple plan for one afternoon.",
      "Describe a small problem you had recently and what you did next.",
    ],
  },
  message: {
    1: [
      "小林：你好！你明天下午有空吗？我们一起喝茶吧。\nReply with whether you are free, a time, and one question.",
      "朋友：我今天不舒服，不能去学校。\nReply kindly and offer one simple suggestion.",
      "妈妈：你晚上回家吃饭吗？\nReply with your plan and what time you will arrive.",
    ],
    2: [
      "朋友：周六我想去爬山，但是天气可能不太好。你觉得呢？\nReply with your opinion and suggest an alternative plan.",
      "同学：下周的考试我还没准备好，你可以跟我一起复习吗？\nReply with when you can help and what to review first.",
      "朋友：我刚搬到你住的城市。附近有什么好吃的？\nRecommend a place or dish and explain why.",
    ],
  },
  translation: {
    1: [
      "Today I am at home. In the morning I drink tea and read a book. In the afternoon, my friend comes to see me.",
      "My older sister is a teacher. She works at a school near our home. We often eat dinner together.",
      "It is raining today, so I do not go to the park. I stay home and watch a Chinese movie.",
    ],
    2: [
      "Yesterday I planned to take the bus, but it arrived too late. I walked to the station and was ten minutes late.",
      "A friend invited me to dinner. The restaurant was crowded, but the food was delicious and not too expensive.",
      "I have studied Chinese for six months. I can understand simple stories, but speaking is still harder than reading.",
    ],
  },
  guided: {
    1: ["Write 3–5 connected sentences. Use at least three of your selected words naturally."],
    2: ["Write a short scene or message. Use at least three of your selected words naturally."],
  },
};

function WritingStudio({ content }: { content: Content }) {
  const [mode, setMode] = useState<WritingMode>("prompt");
  const [level, setLevel] = useState(1);
  const [promptIndex, setPromptIndex] = useState(0);
  const [responseText, setResponseText] = useState("");
  const [attemptId, setAttemptId] = useState(() => crypto.randomUUID());
  const [targetWords, setTargetWords] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<WritingFeedback | null>(null);
  const [message, setMessage] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [history, setHistory] = useState<Array<{
    id: string;
    mode: WritingMode;
    hsk_level: number;
    prompt_text: string;
    response_text: string;
    target_words_json?: string | null;
    feedback_json?: string | null;
    updated_at: string;
  }>>([]);

  const prompts = writingPrompts[mode][level];
  const promptText = prompts[promptIndex % prompts.length];
  const suggestions = useMemo(() => {
    const levelWords = content.words.filter((word) => word.hsk === level);
    const start = (promptIndex * 7 + (mode === "guided" ? 13 : 0)) % Math.max(1, levelWords.length);
    return Array.from({ length: Math.min(8, levelWords.length) }, (_, offset) =>
      levelWords[(start + offset * 11) % levelWords.length],
    );
  }, [content.words, level, mode, promptIndex]);

  useEffect(() => {
    let cancelled = false;
    void loadWritingDraft().then((draft) => {
      if (cancelled || !draft) return;
      setMode(draft.mode);
      setLevel(draft.level);
      setPromptIndex(draft.promptIndex);
      setResponseText(draft.responseText);
      setAttemptId(draft.attemptId);
      setTargetWords(draft.targetWords);
    }).catch(() => undefined).finally(() => {
      if (!cancelled) setDraftLoaded(true);
    });
    void fetch("/api/writing", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : { attempts: [] })
      .then((result: { attempts?: typeof history }) => {
        if (!cancelled) setHistory(result.attempts ?? []);
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!draftLoaded) return;
    const timeout = window.setTimeout(() => {
      void saveWritingDraft({
        mode,
        level,
        promptIndex,
        responseText,
        attemptId,
        targetWords,
      }).catch(() => undefined);
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [attemptId, draftLoaded, level, mode, promptIndex, responseText, targetWords]);

  const chooseMode = (nextMode: WritingMode) => {
    setMode(nextMode);
    setPromptIndex(0);
    setResponseText("");
    setFeedback(null);
    setMessage("");
    setAttemptId(crypto.randomUUID());
    setTargetWords([]);
  };

  const nextPrompt = () => {
    setPromptIndex((index) => index + 1);
    setResponseText("");
    setFeedback(null);
    setMessage("");
    setAttemptId(crypto.randomUUID());
    setTargetWords([]);
  };

  const saveDraft = async () => {
    setMessage("Saving…");
    try {
      const response = await fetch("/api/writing", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ attemptId, id: attemptId, mode, hskLevel: level, promptText, responseText, targetWords }),
      });
      const result = await response.json() as { error?: string };
      if (!response.ok) throw new Error(result.error || "Could not save the draft.");
      setMessage("Draft saved privately.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Saved on this device; cloud save is waiting for a connection.");
    }
  };

  const reviewDraft = async () => {
    if (!responseText.trim()) {
      setMessage("Write a response first. English placeholders are welcome.");
      return;
    }
    setReviewing(true);
    setMessage("Reviewing your meaning, grammar, and vocabulary…");
    try {
      const response = await fetch("/api/writing/review", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ attemptId, mode, hskLevel: level, promptText, responseText, targetWords }),
      });
      const result = await response.json() as { error?: string; feedback?: WritingFeedback };
      if (!response.ok || !result.feedback) throw new Error(result.error || "The review could not finish.");
      setFeedback(result.feedback);
      setMessage("Review ready. Your original draft is preserved below.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The review could not finish.");
    } finally {
      setReviewing(false);
    }
  };

  return (
    <section className="page writing-page">
      <PageHead eyebrow="WRITE · REVISE · REUSE" title="Writing studio" text="Practice useful Chinese without getting stuck on one missing word. Type unknown words in English; the reviewer will translate them and assess the Chinese around them." />

      <div className="writing-mode-grid" aria-label="Writing practice modes">
        {writingModes.map((item) => (
          <button key={item.id} className={mode === item.id ? "active" : ""} onClick={() => chooseMode(item.id)}>
            <strong>{item.label}</strong><span>{item.description}</span>
          </button>
        ))}
      </div>

      <div className="writing-toolbar">
        <label>Level
          <select value={level} onChange={(event) => { setLevel(Number(event.target.value)); setPromptIndex(0); setTargetWords([]); setFeedback(null); }}>
            <option value={1}>HSK 1</option><option value={2}>HSK 2</option>
          </select>
        </label>
        <button onClick={nextPrompt}>New prompt ↻</button>
      </div>

      <div className="writing-workspace">
        <article className="writing-prompt-card">
          <span className="eyebrow">YOUR TASK</span>
          <h2>{mode === "translation" ? "Translate into natural Chinese" : mode === "message" ? "Write your reply" : mode === "guided" ? "Use the target words" : "Respond in Chinese"}</h2>
          <p>{promptText}</p>
          {mode === "guided" && (
            <div className="target-word-picker">
              <span>Choose at least three:</span>
              <div>{suggestions.map((word) => {
                const selected = targetWords.includes(word.hanzi);
                return <button key={word.id} className={selected ? "selected" : ""} onClick={() => setTargetWords((current) => selected ? current.filter((item) => item !== word.hanzi) : [...current, word.hanzi])}><b>{word.hanzi}</b> {word.pinyin} · {word.meaning}</button>;
              })}</div>
            </div>
          )}
        </article>

        <article className="writing-editor-card">
          <label htmlFor="writing-answer">Your Chinese</label>
          <textarea id="writing-answer" value={responseText} onChange={(event) => setResponseText(event.target.value)} placeholder="Write in Chinese. If you do not know a word, type it in English: 我晚上吃 dinner。" />
          <div className="writing-tip"><b>English is allowed.</b><span>Plain English or [brackets] both work. It will be treated as a vocabulary request, not a grammar mistake.</span></div>
          <div className="writing-actions">
            <button onClick={saveDraft}>Save draft</button>
            <button className="primary" onClick={reviewDraft} disabled={reviewing}>{reviewing ? "Reviewing…" : "Review my writing →"}</button>
          </div>
          {message && <p className="writing-message" role="status">{message}</p>}
        </article>
      </div>

      {feedback && <WritingReview answer={responseText} feedback={feedback} />}

      {history.length > 0 && (
        <details className="writing-history">
          <summary>Previous writing · {history.length}</summary>
          <div>{history.slice(0, 8).map((attempt) => (
            <button key={attempt.id} onClick={() => {
              setMode(attempt.mode);
              setLevel(attempt.hsk_level);
              const savedPromptIndex = writingPrompts[attempt.mode][attempt.hsk_level].indexOf(attempt.prompt_text);
              setPromptIndex(savedPromptIndex >= 0 ? savedPromptIndex : 0);
              setResponseText(attempt.response_text);
              setAttemptId(attempt.id);
              try { setTargetWords(attempt.target_words_json ? JSON.parse(attempt.target_words_json) as string[] : []); } catch { setTargetWords([]); }
              try { setFeedback(attempt.feedback_json ? JSON.parse(attempt.feedback_json) as WritingFeedback : null); } catch { setFeedback(null); }
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}>
              <span>{new Date(attempt.updated_at).toLocaleDateString()} · HSK {attempt.hsk_level}</span>
              <strong>{attempt.prompt_text}</strong>
            </button>
          ))}</div>
        </details>
      )}
    </section>
  );
}

function WritingReview({ answer, feedback }: { answer: string; feedback: WritingFeedback }) {
  const sections: Array<[string, ReviewSection]> = [
    ["Task completion", feedback.taskCompletion],
    ["Grammar & word order", feedback.grammarWordOrder],
    ["Vocabulary & naturalness", feedback.vocabularyNaturalness],
    ["Characters & typing", feedback.charactersTyping],
  ];
  return (
    <section className="writing-review" aria-live="polite">
      <header><span className={`review-verdict ${feedback.verdict}`}>{feedback.verdict === "clear" ? "Meaning is clear" : "Revise once"}</span><h2>Writing review</h2><p>{feedback.summary}</p></header>
      <article className="current-answer"><span>YOUR CURRENT DRAFT</span><p>{answer}</p></article>
      {feedback.placeholders.length > 0 && <div className="placeholder-help"><h3>Words you asked for</h3>{feedback.placeholders.map((item, index) => <article key={`${item.english}-${index}`}><span>{item.english}</span><strong>{item.chinese}</strong><em>{item.pinyin}</em><b>{item.hskLevel}</b><p>{item.note}</p></article>)}</div>}
      <div className="review-grid">{sections.map(([label, section]) => <article key={label}><span className={`review-status ${section.status}`}>{section.status}</span><h3>{label}</h3><p>{section.feedback}</p></article>)}</div>
      <article className="corrected-answer"><span>A NATURAL REVISION</span><strong>{feedback.correctedChinese}</strong><button onClick={() => speak(feedback.correctedChinese)}>A · Audio</button></article>
      {feedback.changes.length > 0 && <div className="change-list"><h3>What changed</h3>{feedback.changes.map((change, index) => <p key={index}><del>{change.original}</del><ins>{change.replacement}</ins><span>{change.reason}</span></p>)}</div>}
      <p className="revision-prompt"><b>Try once more:</b> {feedback.revisionPrompt}</p>
    </section>
  );
}

function Vocabulary({
  words,
  allTopics,
  query,
  setQuery,
  hsk,
  setHsk,
  selectedTopics,
  setSelectedTopics,
  practiceFilter,
  setPracticeFilter,
  sort,
  setSort,
  progress,
  updateProgress,
}: {
  words: Word[];
  allTopics: string[];
  query: string;
  setQuery: (value: string) => void;
  hsk: number;
  setHsk: (value: number) => void;
  selectedTopics: string[];
  setSelectedTopics: (value: string[]) => void;
  practiceFilter: string;
  setPracticeFilter: (value: string) => void;
  sort: string;
  setSort: (value: string) => void;
  progress: CloudProgress;
  updateProgress: (id: number, update: (current: VocabularyProgress) => VocabularyProgress) => void;
}) {
  const [practiceMode, setPracticeMode] = useState<"reading" | "listening" | null>(null);
  const [queue, setQueue] = useState<Word[]>([]);
  const [practiceIndex, setPracticeIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const currentWord = queue[practiceIndex];

  const startPractice = (mode: "reading" | "listening") => {
    const prioritized = [...words].sort((a, b) => {
      const aState = progress.vocabulary[String(a.id)];
      const bState = progress.vocabulary[String(b.id)];
      return Number(Boolean(bState?.needsPractice)) - Number(Boolean(aState?.needsPractice))
        || Math.min(aState?.readingScore ?? 101, aState?.listeningScore ?? 101) - Math.min(bState?.readingScore ?? 101, bState?.listeningScore ?? 101)
        || Math.random() - .5;
    }).slice(0, 30);
    setQueue(prioritized);
    setPracticeIndex(0);
    setRevealed(false);
    setPracticeMode(mode);
  };
  const gradeWord = (rating: "again" | "hard" | "good" | "known") => {
    if (!currentWord || !practiceMode) return;
    const target = { again: 15, hard: 45, good: 78, known: 96 }[rating];
    updateProgress(currentWord.id, (state) => {
      const key = practiceMode === "listening" ? "listeningScore" : "readingScore";
      const previous = state[key];
      const score = previous === undefined ? target : Math.round(previous * .65 + target * .35);
      return { ...state, [key]: score, practices: state.practices + 1, lastReviewTs: new Date().toISOString(), needsPractice: rating === "again" || rating === "hard", known: rating === "known" ? true : rating === "again" ? false : state.known };
    });
    setPracticeIndex((index) => index + 1);
    setRevealed(false);
  };

  useEffect(() => {
    if (!practiceMode || !currentWord) return;
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input,textarea,select") || target?.isContentEditable) return;
      if (event.key.toLowerCase() === "a") playAudio(currentWord.hanzi, currentWord.audio);
      else if (!revealed && (event.key === " " || event.key === "Enter")) setRevealed(true);
      else if (revealed && ["1","2","3","4"].includes(event.key)) gradeWord((["again","hard","good","known"] as const)[Number(event.key)-1]);
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  if (practiceMode) {
    if (!currentWord) return <section className="page narrow"><div className="practice-finish"><span className="eyebrow">SESSION COMPLETE</span><h1>{queue.length} words reviewed</h1><p>Your confidence and activity are saved to private cloud progress.</p><button className="primary" onClick={() => setPracticeMode(null)}>Back to vocabulary</button></div></section>;
    return <section className="page narrow vocab-practice">
      <header><button onClick={() => setPracticeMode(null)}>← End session</button><span>{practiceIndex + 1} / {queue.length} · {practiceMode === "listening" ? "Listening" : "Reading"}</span></header>
      <article>
        <span className="eyebrow">{practiceMode === "listening" ? "LISTEN, THEN RECALL" : "READ, THEN RECALL"}</span>
        {practiceMode === "listening" ? <button className="practice-audio" onClick={() => playAudio(currentWord.hanzi,currentWord.audio)}>A · Play audio</button> : <h1>{currentWord.hanzi}</h1>}
        {!revealed ? <button className="reveal" onClick={() => setRevealed(true)}>Reveal answer · Space</button> : <div className="practice-answer"><h2>{currentWord.hanzi}</h2><strong>{currentWord.pinyin}</strong><p>{currentWord.meaning}</p><span>HSK {currentWord.hskLevels.join(" · ")}{currentWord.measureWord ? ` · measure word ${currentWord.measureWord}` : ""}</span></div>}
      </article>
      {revealed && <div className="grade-row"><button onClick={() => gradeWord("again")}><b>1</b> Again</button><button onClick={() => gradeWord("hard")}><b>2</b> Hard</button><button onClick={() => gradeWord("good")}><b>3</b> Good</button><button onClick={() => gradeWord("known")}><b>4</b> Known</button></div>}
      <p className="reader-shortcuts">A audio · Space reveal · 1–4 grade</p>
    </section>;
  }
  return (
    <section className="page">
      <PageHead eyebrow="YOUR KNOWLEDGE MODEL" title="Vocabulary" text="Search and filter the full HSK 1–2 collection. Memory and activity return after you import the local progress export in Settings." />
      <div className="vocabulary-filters">
        <label><span>Search</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Hanzi, pinyin, meaning…" /></label>
        <label><span>HSK level</span><select value={hsk} onChange={(event) => setHsk(Number(event.target.value))}><option value={0}>All levels</option><option value={1}>HSK 1</option><option value={2}>HSK 2</option></select></label>
        <label><span>Topics · multiple</span><select multiple size={2} value={selectedTopics} onChange={(event) => setSelectedTopics([...event.currentTarget.selectedOptions].map((option) => option.value))}>{allTopics.map((topic) => <option key={topic}>{topic}</option>)}</select></label>
        <label><span>Practice status</span><select value={practiceFilter} onChange={(event) => setPracticeFilter(event.target.value)}><option value="all">All words</option><option value="unpracticed">Not practiced</option><option value="practiced">Practiced</option><option value="review">Marked for review</option></select></label>
        <label><span>Sort by</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="hsk">HSK level</option><option value="hanzi">Hanzi</option><option value="practiced">Most practiced</option><option value="last">Recently practiced</option></select></label>
        <button onClick={() => { setQuery(""); setHsk(0); setSelectedTopics([]); setPracticeFilter("all"); setSort("hsk"); }}>Clear</button>
      </div>
      <div className="practice-toolbar"><p className="result-note">Showing {words.length} matching words · practice uses exactly these filters</p><div><button disabled={!words.length} onClick={() => startPractice("reading")}>Practice reading</button><button disabled={!words.length} onClick={() => startPractice("listening")}>Practice listening</button></div></div>
      <div className="vocab-legend"><span><b>Memory</b><i>L</i> listening confidence <i>R</i> reading confidence</span><span><b>Activity</b><i>×</i> practice attempts · time since last practice <i>+R</i> add to review</span></div>
      <div className="word-table">
        <div className="word-row word-head"><span>Hanzi</span><span>Pinyin</span><span>Meaning</span><span>HSK</span><span>Measure</span><span>Memory</span><span>Activity</span></div>
        {words.map((word) => (
          <div className="word-row" key={word.id}>
            <strong><a href={`https://www.mdbg.net/chinese/dictionary?page=worddict&wdrst=0&wdqb=${encodeURIComponent(word.hanzi)}`} target="_blank" rel="noreferrer" title={`Look up ${word.hanzi} in MDBG`}>{word.hanzi} ↗</a><button className="word-audio" aria-label={`Play ${word.hanzi}`} onClick={() => playAudio(word.hanzi, word.audio)}>A</button></strong>
            <span>{word.pinyin}</span><span>{word.meaning}</span>
            <span><i className={`hsk hsk-${word.hsk}`}>HSK {word.hskLevels.join(" · ")}</i></span>
            <span>{word.measureWord || "—"}</span>
            <span><MemoryScores state={progress.vocabulary[String(word.id)]} /></span>
            <span><ActivityCell state={progress.vocabulary[String(word.id)]} onToggle={() => updateProgress(word.id, (current) => {
              const marking = !current.needsPractice;
              return { ...current, needsPractice: marking, known: marking ? false : (word.hsk <= progress.declaredHskBand ? true : current.known) };
            })} /></span>
          </div>
        ))}
      </div>
    </section>
  );
}

function MemoryScores({ state }: { state?: VocabularyProgress }) {
  return <span className="memory-scores"><span><small>L</small><b>{state?.listeningScore !== undefined ? `${state.listeningScore}%` : "—"}</b></span><span><small>R</small><b>{state?.readingScore !== undefined ? `${state.readingScore}%` : "—"}</b></span></span>;
}

function ActivityCell({ state, onToggle }: { state?: VocabularyProgress; onToggle: () => void }) {
  return <span className="activity-cell"><span className="activity-metrics"><b>{state?.practices ?? 0}×</b><small>{relativeTime(state?.lastReviewTs)}</small></span><button className={state?.needsPractice ? "review-toggle active" : "review-toggle"} onClick={onToggle} title={state?.needsPractice ? "Marked for review · click to undo" : "Add to review"}>{state?.needsPractice ? "R✓" : "+R"}</button></span>;
}

function relativeTime(value?: string) {
  if (!value) return "—";
  const elapsed = Date.now() - Date.parse(value);
  if (!Number.isFinite(elapsed) || elapsed < 0) return "—";
  if (elapsed < 3_600_000) return `${Math.max(1, Math.floor(elapsed / 60_000))}m ago`;
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h ago`;
  return `${Math.floor(elapsed / 86_400_000)}d ago`;
}

function Topics({
  topics,
  words,
  progress,
  onOpen,
}: {
  topics: Array<{ name: string; one: number; two: number }>;
  words: Word[];
  progress: CloudProgress;
  onOpen: (name: string, level: number) => void;
}) {
  return (
    <section className="page">
      <PageHead eyebrow="EVERYDAY CHINESE" title="Topics" text="Jump directly into the HSK band and subject you want to explore." />
      <div className="inventory">
        <div><b>HSK 1</b><strong>506 words</strong><span>Foundations loaded</span></div>
        <div><b>HSK 2</b><strong>755 words</strong><span>Elementary loaded</span></div>
        <div className="pending"><b>HSK 3</b><strong>Planned</strong><span>Coming later</span></div>
      </div>
      <div className="topic-grid">
        {topics.map((topic, index) => {
          const bands = [1, 2].map((level) => {
            const matching = words.filter((word) => word.hsk === level && word.topics.includes(topic.name));
            const known = matching.filter((word) => wordIsKnown(word, progress)).length;
            return { level, total: matching.length, known, percent: matching.length ? Math.round(100 * known / matching.length) : 0 };
          });
          return <article key={topic.name}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{topic.name}</h2>
            <div className="topic-band-list">{bands.map((band) => <button key={band.level} onClick={() => onOpen(topic.name, band.level)}><span>HSK {band.level}</span><b>{band.known} / {band.total} known</b><i><em style={{ width: `${band.percent}%` }} /></i><strong>{band.percent}%</strong></button>)}</div>
          </article>;
        })}
      </div>
    </section>
  );
}

function wordIsKnown(word: Word, progress: CloudProgress) {
  const state = progress.vocabulary[String(word.id)];
  if (state?.needsPractice || state?.known === false) return false;
  if (state?.known === true) return true;
  return Boolean(progress.declaredHskBand && word.hsk <= progress.declaredHskBand);
}

function Stories({
  stories,
  storyId,
  sentenceIndex,
  setSentenceIndex,
  openStory,
  closeStory,
  showPinyin,
  setShowPinyin,
  showTranslation,
  setShowTranslation,
  progress,
  vocabularyProgress,
  onCompleteSentence,
  onStatus,
}: {
  stories: Story[];
  storyId: number | null;
  sentenceIndex: number;
  setSentenceIndex: (index: number) => void;
  openStory: (id: number) => void;
  closeStory: () => void;
  showPinyin: boolean;
  setShowPinyin: (value: boolean) => void;
  showTranslation: boolean;
  setShowTranslation: (value: boolean) => void;
  progress: Record<string, StoryProgress>;
  vocabularyProgress: Record<string, VocabularyProgress>;
  onCompleteSentence: (story: Story, index: number, hardWordIds: number[]) => void;
  onStatus: (id: number, status: "new" | "reading" | "finished") => void;
}) {
  const story = stories.find((item) => item.id === storyId);
  const [readerMode, setReaderMode] = useState<"reading" | "listening">("reading");
  const [showCharacters, setShowCharacters] = useState(true);
  const [hardWordOverrides, setHardWordOverrides] = useState<Record<string, number[]>>({});
  const hardWordKey = story ? `${story.id}:${sentenceIndex}` : "";
  const hardWordIds = useMemo(() => hardWordOverrides[hardWordKey]
    ?? (story ? progress[String(story.id)]?.hardWords?.[String(sentenceIndex)] : undefined)
    ?? [], [hardWordKey, hardWordOverrides, progress, sentenceIndex, story]);

  useEffect(() => {
    if (!story) return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select") || target?.isContentEditable || event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      let handled = true;
      if (key === "arrowleft") setSentenceIndex(Math.max(0, sentenceIndex - 1));
      else if (key === "arrowright") {
        onCompleteSentence(story, sentenceIndex, hardWordIds);
        if (sentenceIndex < story.sentences.length - 1) setSentenceIndex(sentenceIndex + 1);
      } else if (key === "a") playAudio(story.sentences[sentenceIndex].zh, story.sentences[sentenceIndex].audio);
      else if (key === "z") setShowCharacters((value) => !value);
      else if (key === "p") setShowPinyin(!showPinyin);
      else if (key === "t") setShowTranslation(!showTranslation);
      else if (key === "m") setReaderMode((value) => value === "reading" ? "listening" : "reading");
      else handled = false;
      if (handled) event.preventDefault();
    };
    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", onKeyDown, { capture: true });
  }, [hardWordIds, onCompleteSentence, sentenceIndex, setSentenceIndex, setShowPinyin, setShowTranslation, showPinyin, showTranslation, story]);

  if (!story) {
    const grouped = new Map<number, Story[]>();
    for (const item of stories) grouped.set(item.hskLevel, [...(grouped.get(item.hskLevel) ?? []), item]);
    return (
      <section className="page">
        <PageHead eyebrow="CONNECTED PRACTICE · 故事" title="Graded stories" text={`${stories.length} readers grouped by target HSK level. Completing a sentence records study progress; mark only the words that still feel hard.`} />
        {[...grouped.entries()].map(([level, levelStories]) => <section className="story-level" key={level}><div className="section-heading"><div><span className="eyebrow">HSK {level} · {level === 1 ? "FOUNDATIONS" : "VOCABULARY EXPANSION"}</span><h2>HSK {level} stories</h2></div><small>{levelStories.length} readers</small></div><div className="story-grid">{levelStories.map((item, index) => {
          const state = progress[String(item.id)];
          const completed = state?.completedSentences?.length ?? (state?.completedAt ? item.sentences.length : 0);
          const hard = Object.values(state?.hardWords ?? {}).flat().length;
          const vocabulary = new Map(item.sentences.flatMap((sentence) => sentence.words).map((word) => [word.id, word]));
          const known = [...vocabulary.values()].filter((word) => {
            const wordState = vocabularyProgress[String(word.id)];
            return !wordState?.needsPractice && wordState?.known === true;
          }).length;
          const knownPercent = Math.round(100 * known / Math.max(1, vocabulary.size));
          return <article className="story-card" key={item.id}><div className="story-card-top"><span>HSK {level} · STORY {String(index + 1).padStart(2, "0")}</span><select value={state?.status ?? (state?.completedAt ? "finished" : "new")} onChange={(event) => onStatus(item.id, event.target.value as "new" | "reading" | "finished")} aria-label={`Status for ${item.titleEn}`}><option value="new">New</option><option value="reading">Reading</option><option value="finished">Finished</option></select></div><strong>{item.titleZh}</strong><em>{item.titleEn} · {item.sentences.length} sentences</em><div className="story-card-progress"><span>{completed} / {item.sentences.length} sentences studied</span><i><b style={{ width: `${100 * completed / item.sentences.length}%` }} /></i></div>{hard > 0 && <small>{hard} hard word{hard === 1 ? "" : "s"} queued for review</small>}<div className="story-known"><b>{knownPercent}%</b><span>vocabulary known · {known} of {vocabulary.size}</span></div><button onClick={() => openStory(item.id)}>{state?.status === "reading" ? "Resume reader" : "Open reader"} →</button></article>;
        })}</div></section>)}
      </section>
    );
  }
  const sentence = story.sentences[sentenceIndex];
  const percent = Math.round(((sentenceIndex + 1) / story.sentences.length) * 100);
  const storyState = progress[String(story.id)];
  const completedCount = storyState?.completedSentences?.length ?? (storyState?.completedAt ? story.sentences.length : 0);
  const completeAndMove = () => {
    onCompleteSentence(story, sentenceIndex, hardWordIds);
    if (sentenceIndex < story.sentences.length - 1) setSentenceIndex(sentenceIndex + 1);
  };
  return (
    <section className="reader">
      <header><button onClick={closeStory}>← All stories</button><div><span>HSK {story.hskLevel} · {story.titleEn}</span><strong>{story.titleZh}</strong></div><button className="reader-mode" onClick={() => { const next = readerMode === "reading" ? "listening" : "reading"; setReaderMode(next); if (next === "listening") playAudio(sentence.zh, sentence.audio); }}>{readerMode === "reading" ? "Reading mode" : "Listening mode"}</button></header>
      <div className="reader-state"><label>Story status <select value={storyState?.status ?? (storyState?.completedAt ? "finished" : "new")} onChange={(event) => onStatus(story.id, event.target.value as "new" | "reading" | "finished")}><option value="new">New</option><option value="reading">Reading</option><option value="finished">Finished</option></select></label><span>{completedCount} of {story.sentences.length} sentences studied</span></div>
      <div className="reader-count"><span>{sentenceIndex + 1} / {story.sentences.length}</span></div>
      <div className="reader-meter"><i style={{ width: `${percent}%` }} /></div>
      <article>
        <span className="eyebrow">{readerMode === "reading" ? "READ" : "LISTEN"} · SENTENCE {sentenceIndex + 1}</span>
        {showCharacters && readerMode === "reading" && <h2>{sentence.zh}</h2>}
        {showPinyin && <p className="reader-pinyin">{sentence.pinyin}</p>}
        {showTranslation && <p className="reader-translation">{sentence.en}</p>}
        {readerMode === "listening" && !showCharacters && <button className="listen-again" onClick={() => playAudio(sentence.zh, sentence.audio)}>A · Play audio</button>}
      </article>
      <section className="reader-vocabulary"><div><span>VOCABULARY IN THIS SENTENCE</span><p>Going next records this sentence. Toggle only words that still need practice.</p></div><div>{sentence.words.map((word) => { const hard = hardWordIds.includes(word.id); return <label className={hard ? "reader-word hard" : "reader-word"} key={word.id}><input type="checkbox" checked={hard} onChange={() => setHardWordOverrides((current) => ({ ...current, [hardWordKey]: hard ? hardWordIds.filter((id) => id !== word.id) : [...hardWordIds, word.id] }))} /><b>{word.hanzi}</b><span>{word.pinyin} · {word.meaning}</span><em>{hard ? "Hard ✓" : "Mark hard"}</em></label>; })}</div>{storyState?.completedSentences?.includes(sentenceIndex) && <p>✓ Already in your study history. You can still change its hard words.</p>}</section>
      <div className="reader-controls">
        <button onClick={() => setSentenceIndex(Math.max(0, sentenceIndex - 1))} disabled={sentenceIndex === 0}>← Previous</button>
        <button onClick={() => playAudio(sentence.zh, sentence.audio)}>A · Audio</button>
        <button className={showCharacters ? "active" : ""} onClick={() => setShowCharacters(!showCharacters)}>Z · Characters</button>
        <button className={showPinyin ? "active" : ""} onClick={() => setShowPinyin(!showPinyin)}>P · Pinyin</button>
        <button className={showTranslation ? "active" : ""} onClick={() => setShowTranslation(!showTranslation)}>T · Translation</button>
        <button onClick={completeAndMove}>{sentenceIndex === story.sentences.length - 1 ? "Finish story ✓" : "Next →"}</button>
      </div>
      <p className="reader-shortcuts">← → move · A audio · Z characters · P pinyin · T translation · M mode</p>
    </section>
  );
}

function GrammarLibrary({
  lessons,
  selectedId,
  setSelectedId,
  statuses,
  setStatus,
}: {
  lessons: Grammar[];
  selectedId: number | null;
  setSelectedId: (id: number | null) => void;
  statuses: Record<string, GrammarStatus>;
  setStatus: (id: number, status: GrammarStatus) => void;
}) {
  const [level, setLevel] = useState(1);
  const [practice, setPractice] = useState<{ lesson: Grammar; direction: "zh_en" | "en_zh" } | null>(null);
  const selected = lessons.find((lesson) => lesson.id === selectedId);
  if (practice) return <GrammarPractice lesson={practice.lesson} direction={practice.direction} onBack={() => setPractice(null)} onStatus={setStatus} />;
  if (selected) {
    return (
      <section className="grammar-detail">
        <button className="back" onClick={() => setSelectedId(null)}>← Grammar library</button>
        <span className="eyebrow">HSK {selected.level} · GRAMMAR LESSON</span>
        {selected.recommendedEarly && <span className="recommended-chip">◆ Recommended early</span>}
        <h1>{selected.titleEn}</h1><h2>{selected.titleZh}</h2>
        <div className="pattern"><span>STRUCTURE</span><strong>{selected.pattern}</strong></div>
        <label className="lesson-status">Learning status
          <select
            value={statuses[String(selected.id)] ?? "new"}
            onChange={(event) => setStatus(selected.id, event.target.value as GrammarStatus)}
          >
            <option value="new">New</option>
            <option value="practicing">Practicing</option>
            <option value="learned">Learned</option>
          </select>
        </label>
        <p className="explanation">{selected.explanation}</p>
        <div className="grammar-actions"><button className="primary" onClick={() => setPractice({ lesson:selected,direction:"zh_en" })}>Practice Chinese → English</button><button onClick={() => setPractice({ lesson:selected,direction:"en_zh" })}>Practice English → Chinese</button><a href={`https://resources.allsetlearning.com/chinese/grammar/HSK_${selected.level}_grammar_points`} target="_blank" rel="noreferrer">Read more on Chinese Grammar Wiki ↗</a></div>
        <h3>Worked examples</h3>
        <div className="examples">
          {selected.examples.map((example, index) => (
            <article key={`${example.zh}-${index}`}><div><b>{example.zh}</b><small>{example.pinyin}</small></div><p>{example.en}</p><button onClick={() => playAudio(example.zh, example.audio)}>A · Audio</button></article>
          ))}
        </div>
      </section>
    );
  }
  const filtered = lessons.filter((lesson) => lesson.level === level);
  return (
    <section className="page">
      <PageHead eyebrow="STRUCTURE WITH PURPOSE" title="Grammar" text="Clear HSK-organized lessons with patterns and natural examples." />
      <div className="level-tabs">{[1, 2, 3].map((item) => <button className={level === item ? "active" : ""} key={item} onClick={() => setLevel(item)}>HSK {item} · {lessons.filter((lesson) => lesson.level === item).length}</button>)}</div>
      <div className="grammar-grid">
        {filtered.map((lesson, index) => (
          <button key={lesson.id} onClick={() => setSelectedId(lesson.id)}>
            <span>LESSON {String(index + 1).padStart(2, "0")} · {grammarStatusLabel(statuses[String(lesson.id)] ?? "new")}</span>{lesson.recommendedEarly && <b className="recommended-chip">◆ Recommended early</b>}<strong>{lesson.titleEn}</strong><em>{lesson.titleZh}</em><code>{lesson.pattern}</code>
          </button>
        ))}
      </div>
    </section>
  );
}

type GrammarFeedback = {
  verdict: "correct" | "needs_revision";
  targetGrammarCorrect: boolean;
  summary: string;
  explanation: string;
  correctedAnswer: string;
  vocabularyHelp: Array<{ english: string; chinese: string; pinyin: string; hskLevel: string }>;
  differences: Array<{ learner: string; suggested: string; reason: string }>;
};

function GrammarPractice({ lesson, direction, onBack, onStatus }: { lesson: Grammar; direction: "zh_en" | "en_zh"; onBack: () => void; onStatus: (id:number,status:GrammarStatus)=>void }) {
  const [queue] = useState(() => [...(lesson.practiceExamples.length ? lesson.practiceExamples : lesson.examples)].sort(() => Math.random()-.5));
  const [index,setIndex] = useState(0);
  const [answer,setAnswer] = useState("");
  const [attemptId,setAttemptId] = useState("");
  const [submitted,setSubmitted] = useState(false);
  const [feedback,setFeedback] = useState<GrammarFeedback|null>(null);
  const [message,setMessage] = useState("");
  const [question,setQuestion] = useState("");
  const [asking,setAsking] = useState(false);
  const example = queue[index];
  const prompt = direction === "en_zh" ? example?.en : example?.zh;
  const expected = direction === "en_zh" ? example?.zh : example?.en;
  const normalizedExact = Boolean(answer && expected && normalizeAnswer(answer) === normalizeAnswer(expected));

  const next = () => { setIndex((value)=>value+1);setAnswer("");setSubmitted(false);setFeedback(null);setAttemptId("");setMessage("");setQuestion(""); };
  const submit = async () => {
    if (!answer.trim() || !example) return;
    setSubmitted(true); setMessage("Saving your attempt…"); onStatus(lesson.id,"practicing");
    try {
      const response = await fetch("/api/grammar/attempts",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({grammarId:lesson.id,direction,prompt,response:answer,expected,verdict:normalizedExact?"correct":"pending"})});
      const result = await response.json() as {id?:string;error?:string};
      if (!response.ok || !result.id) throw new Error(result.error||"Could not save the attempt.");
      setAttemptId(result.id);setMessage(normalizedExact ? "Exact match — correct." : "Saved. This is not marked wrong: compare it yourself or ask AI to verify natural alternatives.");
    } catch(error) { setMessage(error instanceof Error?error.message:"Could not save the attempt."); }
  };
  const askAi = async () => {
    if (!submitted || !attemptId) return;
    setAsking(true);setMessage("Asking the Mandarin tutor…");
    try {
      const response = await fetch("/api/grammar/review",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({attemptId,lesson:`HSK ${lesson.level} · ${lesson.titleEn}`,pattern:lesson.pattern,prompt,answer,expected,question})});
      const result = await response.json() as {feedback?:GrammarFeedback;error?:string};
      if (!response.ok || !result.feedback) throw new Error(result.error||"The review could not be completed.");
      setFeedback(result.feedback);setQuestion("");setMessage("");
    } catch(error) { setMessage(error instanceof Error?error.message:"The review could not be completed."); }
    finally { setAsking(false); }
  };
  const flagAndSkip = async () => {
    if (!example) return;
    setMessage("Flagging this exercise…");
    try { await fetch("/api/reports",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({kind:"grammar_exercise",referenceId:`grammar:${lesson.id}:${index}`,note:"Flagged and skipped during grammar practice",context:{lesson:lesson.titleEn,pattern:lesson.pattern,prompt,expected,answer}})}); }
    finally { next(); }
  };

  if (!example) return <section className="page narrow"><div className="practice-finish"><span className="eyebrow">LESSON PRACTICE COMPLETE</span><h1>{queue.length} different examples practiced</h1><p>Your attempts are saved. Mark the lesson learned when the pattern feels comfortable.</p><div><button onClick={onBack}>Back to lesson</button><button className="primary" onClick={()=>{onStatus(lesson.id,"learned");onBack();}}>Mark learned</button></div></div></section>;
  return <section className="page grammar-practice">
    <header className="practice-header"><button onClick={onBack}>← Back to {lesson.titleEn}</button><span>HSK {lesson.level} · {index+1}/{queue.length}</span></header>
    <div className="practice-layout"><article className="exercise-card"><span className="eyebrow">{direction === "en_zh" ? "TRANSLATE INTO CHINESE" : "TRANSLATE INTO ENGLISH"}</span><h1>{prompt}</h1>{direction === "zh_en" && <><p className="reader-pinyin">{example.pinyin}</p><button className="word-audio" onClick={()=>playAudio(example.zh,example.audio)}>A · Audio</button></>}<label>Your answer<textarea value={answer} onChange={(event)=>setAnswer(event.target.value)} disabled={submitted} placeholder={direction === "en_zh" ? "Write Chinese here. English placeholders are okay for words you do not know." : "Write a natural English translation."} /></label>{!submitted ? <button className="primary submit-answer" onClick={()=>void submit()} disabled={!answer.trim()}>Check answer</button> : <div className="model-answer"><span>MODEL ANSWER</span><strong>{expected}</strong>{direction === "en_zh" && <small>{example.pinyin}</small>}<p>{message}</p></div>}</article>
      <aside className="practice-side"><span className="eyebrow">TARGET PATTERN</span><strong>{lesson.pattern}</strong><p>{lesson.titleEn}</p>{submitted && <><button className="primary" onClick={()=>void askAi()} disabled={asking}>{asking?"Checking…":"Ask AI to verify & explain"}</button><label>Follow-up question<textarea value={question} onChange={(event)=>setQuestion(event.target.value)} placeholder="Why is this more natural? Could my version also be correct?" /></label>{feedback && <div className="grammar-feedback"><b className={feedback.verdict}>{feedback.verdict === "correct"?"Correct":"Needs revision"}</b><h3>{feedback.summary}</h3><p>{feedback.explanation}</p><div><span>NATURAL ANSWER</span><strong>{feedback.correctedAnswer}</strong></div>{feedback.vocabularyHelp.length>0&&<ul>{feedback.vocabularyHelp.map((item,i)=><li key={i}><b>{item.english}</b> → {item.chinese} · {item.pinyin} <em>{item.hskLevel}</em></li>)}</ul>}{feedback.differences.length>0&&<ul>{feedback.differences.map((item,i)=><li key={i}><b>{item.learner||"Your version"}</b> → {item.suggested}: {item.reason}</li>)}</ul>}</div>}<div className="practice-secondary"><button onClick={()=>void flagAndSkip()}>Flag & skip</button><button onClick={next}>Next →</button></div></>}</aside></div>
  </section>;
}

function normalizeAnswer(value:string) { return value.toLowerCase().replace(/[\s，。！？、,.!?;；:：'"“”‘’]/g,""); }

type ExternalReading = { id:string;provider:"mandarinbean"|"hskreading";hsk_level:number;title:string;url:string;status:"new"|"in_progress"|"completed";hard_words:string;notes:string;updated_at:string };

function Comprehension() {
  const [provider,setProvider] = useState<"mandarinbean"|"hskreading">("hskreading");
  const [level,setLevel] = useState(1);
  const [readings,setReadings] = useState<ExternalReading[]>([]);
  const [url,setUrl] = useState("");
  const [title,setTitle] = useState("");
  const [hardWords,setHardWords] = useState("");
  const [notes,setNotes] = useState("");
  const [status,setStatus] = useState<ExternalReading["status"]>("completed");
  const [message,setMessage] = useState("");
  const [saving,setSaving] = useState(false);
  const load = () => void fetch("/api/comprehension",{cache:"no-store"}).then(async(response)=>{if(!response.ok)throw new Error();return response.json() as Promise<{readings:ExternalReading[]}>;}).then((result)=>setReadings(result.readings)).catch(()=>setMessage("Saved readers are temporarily unavailable."));
  useEffect(load,[]);
  const addReading = async () => {
    if (!url.trim()) return;
    setSaving(true);setMessage("Saving reader…");
    try {
      const response=await fetch("/api/comprehension",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({provider,hskLevel:level,url,title,hardWords,notes,status})});
      const result=await response.json() as {error?:string};if(!response.ok)throw new Error(result.error||"Could not save the reader.");
      setUrl("");setTitle("");setHardWords("");setNotes("");setMessage("Reader saved.");load();
    } catch(error){setMessage(error instanceof Error?error.message:"Could not save the reader.");} finally{setSaving(false);}
  };
  const updateStatus=async(reading:ExternalReading,next:ExternalReading["status"])=>{await fetch("/api/comprehension",{method:"PATCH",headers:{"content-type":"application/json"},body:JSON.stringify({id:reading.id,status:next})});setReadings((current)=>current.map((item)=>item.id===reading.id?{...item,status:next}:item));};
  const openReading=(reading:ExternalReading)=>{void updateStatus(reading,reading.status==="completed"?"completed":"in_progress");window.open(reading.url,"_blank","noopener,noreferrer");};
  const sourceUrl=provider==="mandarinbean"?"https://mandarinbean.com/all-lessons/":`https://hskreading.com/category/hsk-${level}/`;
  const filtered=readings.filter((item)=>item.provider===provider&&item.hsk_level===level);
  return <section className="page comprehension-page"><PageHead eyebrow="EXTERNAL READING & LISTENING" title="Comprehension" text="Use authoritative graded readers, then save the exact article, status, hard words, and notes to your private Hanlu account." />
    <div className="source-tabs"><button className={provider==="hskreading"?"active":""} onClick={()=>setProvider("hskreading")}>HSKReading</button><button className={provider==="mandarinbean"?"active":""} onClick={()=>setProvider("mandarinbean")}>MandarinBean</button></div>
    <section className="source-hero"><div><span className="eyebrow">{provider === "hskreading" ? `HSK ${level} LIBRARY` : "ALL-LEVEL LIBRARY"}</span><h2>{provider === "hskreading" ? "HSKReading" : "MandarinBean"}</h2><p>{provider === "hskreading" ? "Free level-specific readings with questions, pinyin, translation, and voice-over." : "Graded reading and listening lessons across HSK levels. Choose a level on their library page."}</p></div><a href={sourceUrl} target="_blank" rel="noreferrer">Open {provider === "hskreading" ? `HSK ${level} readers` : "MandarinBean library"} ↗</a></section>
    <div className="level-tabs">{[1,2,3,4,5,6].map((item)=><button key={item} className={level===item?"active":""} onClick={()=>setLevel(item)}>HSK {item}</button>)}</div>
    <div className="comprehension-layout"><section><div className="section-heading"><div><span className="eyebrow">YOUR READING LOG</span><h2>HSK {level} · {filtered.length} saved</h2></div></div>{filtered.length===0?<div className="empty-reader"><h3>No saved readers at this level yet.</h3><p>Open the source library, complete one article, then save its exact URL here.</p></div>:<div className="saved-readers">{filtered.map((reading)=><article key={reading.id}><div><span className="reading-provider">{reading.status.replace("_"," ")}</span><button className="reading-title" onClick={()=>openReading(reading)}>{reading.title} ↗</button>{reading.hard_words&&<p><b>Hard words:</b> {reading.hard_words}</p>}{reading.notes&&<p>{reading.notes}</p>}</div><select value={reading.status} onChange={(event)=>void updateStatus(reading,event.target.value as ExternalReading["status"])} aria-label={`Status for ${reading.title}`}><option value="new">New</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></article>)}</div>}</section>
      <aside className="add-reader"><span className="eyebrow">ADD A READER</span><h2>Save what you studied</h2><label>Exact article URL<input value={url} onChange={(event)=>setUrl(event.target.value)} placeholder={provider==="hskreading"?"https://hskreading.com/article-name/":"https://mandarinbean.com/article-name/"} /></label><label>Title <small>optional — inferred from URL</small><input value={title} onChange={(event)=>setTitle(event.target.value)} placeholder="Reader title" /></label><label>Hard words<textarea value={hardWords} onChange={(event)=>setHardWords(event.target.value)} placeholder="晚餐 — dinner / evening meal" /></label><label>Notes <small>optional</small><textarea value={notes} onChange={(event)=>setNotes(event.target.value)} placeholder="What was difficult or useful?" /></label><label>Status<select value={status} onChange={(event)=>setStatus(event.target.value as ExternalReading["status"])}><option value="new">New</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></label><button className="primary" disabled={saving||!url.trim()} onClick={()=>void addReading()}>{saving?"Saving…":"Save reader"}</button>{message&&<p role="status">{message}</p>}</aside></div>
  </section>;
}

function Progress({
  content,
  progress,
  syncState,
}: {
  content: Content;
  progress: CloudProgress;
  syncState: SyncState;
}) {
  const completedStories = content.stories.filter(
    (story) => progress.stories[String(story.id)]?.completedAt,
  ).length;
  const practicingGrammar = Object.values(progress.grammar).filter(
    (status) => status === "practicing",
  ).length;
  const learnedGrammar = Object.values(progress.grammar).filter(
    (status) => status === "learned",
  ).length;
  const knownVocabulary = content.words.filter((word) => wordIsKnown(word, progress)).length;
  const markedVocabulary = Object.values(progress.vocabulary).filter((state) => state.needsPractice).length;
  return (
    <section className="page narrow">
      <PageHead eyebrow="PRIVATE CLOUD PROGRESS" title="Progress" text="Story reading and grammar-study status follow you between signed-in devices." />
      <div className="progress-grid">
        <article><span>Stories completed</span><strong>{completedStories} / {content.stories.length}</strong></article>
        <article><span>Vocabulary known</span><strong>{knownVocabulary} / {content.words.length}</strong></article>
        <article><span>Marked for review</span><strong>{markedVocabulary}</strong></article>
        <article><span>Grammar in progress</span><strong>{practicingGrammar}</strong></article>
        <article><span>Grammar learned</span><strong>{learnedGrammar}</strong></article>
      </div>
      <div className="notice-card"><span>{syncState === "saved" ? "SAVED PRIVATELY" : "SAVED ON THIS DEVICE"}</span><h2>{syncState === "saved" ? "Your progress is synced." : "Your progress will sync when this device is back online."}</h2><p>The original local tutor remains unchanged on this laptop. Use Settings to import a fresh local progress export; Hanlu keeps an exact private backup before creating the cloud summary.</p><strong>Filtered vocabulary review, grammar practice, writing review, and external-reader tracking are available in the private cloud app.</strong></div>
    </section>
  );
}

function Settings({ syncState, onImported }: { syncState: SyncState; onImported: (progress: CloudProgress) => void }) {
  const [importState, setImportState] = useState("");
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const importProgress = async () => {
    if (!selectedFile) return;
    setImporting(true);
    setImportState("Reading and validating the local export…");
    try {
      const payload = JSON.parse(await selectedFile.text()) as unknown;
      const response = await fetch("/api/progress/import", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json() as { error?: string; progress?: CloudProgress; imported?: { vocabulary: number; reviews: number; stories: number; grammar: number } };
      if (!response.ok || !result.progress || !result.imported) throw new Error(result.error || "The import could not be completed.");
      onImported(result.progress);
      setImportState(`Imported ${result.imported.vocabulary} vocabulary records, ${result.imported.reviews} reviews, ${result.imported.stories} stories, and ${result.imported.grammar} grammar statuses. An exact private backup was retained.`);
      setSelectedFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      setImportState(error instanceof Error ? error.message : "The import could not be completed.");
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="page narrow">
      <PageHead eyebrow="PRIVATE CLOUD SETTINGS" title="Settings" text="Keep the hosted app aligned with the richer local Hanlu data without overwriting the laptop database." />
      <section className="import-card">
        <span className="eyebrow">RESTORE LOCAL PROGRESS</span>
        <h2>Import a Hanlu progress export</h2>
        <p>Choose a fresh Hanlu JSON export. Nothing is uploaded until you press <b>Import selected file</b>. An exact private recovery copy is retained.</p>
        <div className="import-picker"><input ref={fileInput} id="progress-import" type="file" accept="application/json,.json" disabled={importing} onChange={(event) => { setSelectedFile(event.target.files?.[0] ?? null); setImportState(""); }} /><label htmlFor="progress-import" className={importing ? "disabled" : ""}>{selectedFile ? "Choose another file" : "Choose JSON file"}</label><div><strong>{selectedFile?.name ?? "No file selected"}</strong><span>{selectedFile ? `${Math.max(1,Math.round(selectedFile.size/1024))} KB · ready to import` : "Recommended: Hanlu-progress-2026-08-19.json in Downloads"}</span></div><button className="primary" disabled={!selectedFile||importing} onClick={()=>void importProgress()}>{importing?"Importing…":"Import selected file"}</button></div>
        {importState && <p className="import-state" role="status">{importState}</p>}
      </section>
      <div className="settings-list">
        <article><b>Hosted curriculum</b><span>1,261 words · 18 stories · 90 grammar lessons</span></article>
        <article><b>Audio</b><span>Uses the same cached Mandarin neural clips as the local tutor, with device speech only as a fallback.</span></article>
        <article><b>Cloud progress</b><span>{syncState === "saved" ? "Vocabulary, story, and grammar status sync privately across signed-in devices." : "Waiting for an internet connection before syncing."}</span></article>
        <article><b>Hosted offline access</b><span>After one successful online visit, the app shell and curriculum are cached on this device. Private progress API responses are never cached.</span></article>
        <article><b>Offline learning data</b><span>Your existing local tutor data remains on your laptop and is never uploaded automatically.</span></article>
        <article><b>Open source</b><a href="https://github.com/josecoves/hanlu-chinese-tutor" target="_blank" rel="noreferrer">View source on GitHub ↗</a></article>
      </div>
    </section>
  );
}

function grammarStatusLabel(status: GrammarStatus) {
  return status === "new" ? "NEW" : status.toUpperCase();
}

function PageHead({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return <header className="page-head"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{text}</p></header>;
}
