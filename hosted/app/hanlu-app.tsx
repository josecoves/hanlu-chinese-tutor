"use client";

import { useEffect, useMemo, useState } from "react";
import { loadOfflineProgress, saveOfflineProgress } from "./offline-progress";
import { loadWritingDraft, saveWritingDraft } from "./offline-writing";

type Word = {
  id: number;
  hanzi: string;
  pinyin: string;
  meaning: string;
  hsk: number;
  topics: string[];
};
type Sentence = { zh: string; pinyin: string; en: string };
type Story = {
  id: number;
  titleZh: string;
  titleEn: string;
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
  examples: Array<{ zh: string; en: string }>;
};
type Content = { words: Word[]; stories: Story[]; grammar: Grammar[] };
type StoryProgress = { sentenceIndex: number; completedAt?: string };
type GrammarStatus = "new" | "practicing" | "learned";
type CloudProgress = {
  version: 1;
  stories: Record<string, StoryProgress>;
  grammar: Record<string, GrammarStatus>;
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
  | "Writing"
  | "Grammar"
  | "Progress"
  | "Settings";

const tabs: Tab[] = [
  "Today",
  "Vocabulary",
  "Topics",
  "Stories",
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

export function HanluApp({ content }: { content: Content }) {
  const [tab, setTab] = useState<Tab>("Today");
  const [query, setQuery] = useState("");
  const [hsk, setHsk] = useState(0);
  const [storyId, setStoryId] = useState<number | null>(null);
  const [sentenceIndex, setSentenceIndex] = useState(0);
  const [showPinyin, setShowPinyin] = useState(true);
  const [showTranslation, setShowTranslation] = useState(false);
  const [grammarId, setGrammarId] = useState<number | null>(null);
  const [progress, setProgress] = useState<CloudProgress>({
    version: 1,
    stories: {},
    grammar: {},
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
        if (remoteProgress?.version === 1) {
          setProgress(remoteProgress);
          void saveOfflineProgress(remoteProgress);
        }
        setCanSyncProgress(true);
        setSyncState("saved");
      })
      .catch(async () => {
        try {
          const cachedProgress = await loadOfflineProgress<CloudProgress>();
          if (!cancelled && cachedProgress?.version === 1) {
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
    return content.words
      .filter((word) => !hsk || word.hsk === hsk)
      .filter(
        (word) =>
          !needle ||
          word.hanzi.includes(needle) ||
          word.pinyin.toLowerCase().includes(needle) ||
          word.meaning.toLowerCase().includes(needle) ||
          word.topics.some((topic) => topic.toLowerCase().includes(needle)),
      )
      .slice(0, 250);
  }, [content.words, hsk, query]);

  const openTopic = (name: string, level: number) => {
    setQuery(name);
    setHsk(level);
    setTab("Vocabulary");
  };

  const openStory = (id: number) => {
    setStoryId(id);
    setSentenceIndex(progress.stories[String(id)]?.sentenceIndex ?? 0);
    setShowPinyin(true);
    setShowTranslation(false);
  };

  const updateStoryProgress = (id: number, index: number, total: number) => {
    setCanSyncProgress(true);
    setProgress((current) => ({
      ...current,
      stories: {
        ...current.stories,
        [id]: {
          sentenceIndex: index,
          ...(index >= total - 1 ? { completedAt: new Date().toISOString() } : {}),
        },
      },
    }));
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
            query={query}
            setQuery={setQuery}
            hsk={hsk}
            setHsk={setHsk}
          />
        )}
        {tab === "Topics" && (
          <Topics topics={topics} onOpen={openTopic} />
        )}
        {tab === "Stories" && (
          <Stories
            stories={content.stories}
            storyId={storyId}
            sentenceIndex={sentenceIndex}
            setSentenceIndex={(index) => {
              setSentenceIndex(index);
              if (storyId !== null) {
                const story = content.stories.find((item) => item.id === storyId);
                if (story) updateStoryProgress(storyId, index, story.sentences.length);
              }
            }}
            openStory={openStory}
            closeStory={() => setStoryId(null)}
            showPinyin={showPinyin}
            setShowPinyin={setShowPinyin}
            showTranslation={showTranslation}
            setShowTranslation={setShowTranslation}
            progress={progress.stories}
          />
        )}
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
        {tab === "Settings" && <Settings syncState={syncState} />}
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
  query,
  setQuery,
  hsk,
  setHsk,
}: {
  words: Word[];
  query: string;
  setQuery: (value: string) => void;
  hsk: number;
  setHsk: (value: number) => void;
}) {
  return (
    <section className="page">
      <PageHead eyebrow="PRACTICAL LEXICON" title="Vocabulary" text="Search the full HSK 1–2 collection by Hanzi, pinyin, meaning, or topic." />
      <div className="filters">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search words, meanings, or topics" aria-label="Search vocabulary" />
        <select value={hsk} onChange={(event) => setHsk(Number(event.target.value))} aria-label="Filter by HSK level">
          <option value={0}>All HSK levels</option><option value={1}>HSK 1</option><option value={2}>HSK 2</option>
        </select>
        <button onClick={() => { setQuery(""); setHsk(0); }}>Clear</button>
      </div>
      <p className="result-note">Showing {words.length} matching words</p>
      <div className="word-table">
        <div className="word-row word-head"><span>Word</span><span>Pinyin</span><span>Meaning</span><span>Level</span><span /></div>
        {words.map((word) => (
          <div className="word-row" key={word.id}>
            <strong>{word.hanzi}</strong><span>{word.pinyin}</span><span>{word.meaning}</span>
            <span><i className={`hsk hsk-${word.hsk}`}>HSK {word.hsk}</i></span>
            <button aria-label={`Play ${word.hanzi}`} onClick={() => speak(word.hanzi)}>A · Audio</button>
          </div>
        ))}
      </div>
    </section>
  );
}

function Topics({
  topics,
  onOpen,
}: {
  topics: Array<{ name: string; one: number; two: number }>;
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
        {topics.map((topic, index) => (
          <article key={topic.name}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{topic.name}</h2>
            <div><button onClick={() => onOpen(topic.name, 1)}>HSK 1 · {topic.one} words</button><button onClick={() => onOpen(topic.name, 2)}>HSK 2 · {topic.two} words</button></div>
          </article>
        ))}
      </div>
    </section>
  );
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
}) {
  const story = stories.find((item) => item.id === storyId);
  if (!story) {
    return (
      <section className="page">
        <PageHead eyebrow="READING LIBRARY" title="Stories" text="Short original stories designed for HSK 1–2 learners." />
        <div className="story-grid">
          {stories.map((item, index) => (
            <button key={item.id} onClick={() => openStory(item.id)}>
              <span>{storyProgressLabel(index + 1, item, progress[String(item.id)])}</span>
              <strong>{item.titleZh}</strong><em>{item.titleEn}</em><b>Start reading →</b>
            </button>
          ))}
        </div>
      </section>
    );
  }
  const sentence = story.sentences[sentenceIndex];
  const percent = Math.round(((sentenceIndex + 1) / story.sentences.length) * 100);
  return (
    <section className="reader">
      <header><button onClick={closeStory}>← All stories</button><div><span>{story.titleEn}</span><strong>{story.titleZh}</strong></div><b>{sentenceIndex + 1} / {story.sentences.length}</b></header>
      <div className="reader-meter"><i style={{ width: `${percent}%` }} /></div>
      <article>
        <span className="eyebrow">READ · SENTENCE {sentenceIndex + 1}</span>
        <h2>{sentence.zh}</h2>
        {showPinyin && <p className="reader-pinyin">{sentence.pinyin}</p>}
        {showTranslation && <p className="reader-translation">{sentence.en}</p>}
      </article>
      <div className="reader-controls">
        <button onClick={() => setSentenceIndex(Math.max(0, sentenceIndex - 1))} disabled={sentenceIndex === 0}>← Previous</button>
        <button onClick={() => speak(sentence.zh)}>A · Audio</button>
        <button className={showPinyin ? "active" : ""} onClick={() => setShowPinyin(!showPinyin)}>P · Pinyin</button>
        <button className={showTranslation ? "active" : ""} onClick={() => setShowTranslation(!showTranslation)}>T · Translation</button>
        <button onClick={() => setSentenceIndex(Math.min(story.sentences.length - 1, sentenceIndex + 1))} disabled={sentenceIndex === story.sentences.length - 1}>Next →</button>
      </div>
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
  const selected = lessons.find((lesson) => lesson.id === selectedId);
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
        <h3>Worked examples</h3>
        <div className="examples">
          {selected.examples.map((example, index) => (
            <article key={`${example.zh}-${index}`}><b>{example.zh}</b><p>{example.en}</p><button onClick={() => speak(example.zh)}>A · Audio</button></article>
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
  return (
    <section className="page narrow">
      <PageHead eyebrow="PRIVATE CLOUD PROGRESS" title="Progress" text="Story reading and grammar-study status follow you between signed-in devices." />
      <div className="progress-grid">
        <article><span>Stories completed</span><strong>{completedStories} / {content.stories.length}</strong></article>
        <article><span>Grammar in progress</span><strong>{practicingGrammar}</strong></article>
        <article><span>Grammar learned</span><strong>{learnedGrammar}</strong></article>
      </div>
      <div className="notice-card"><span>{syncState === "saved" ? "SAVED PRIVATELY" : "SAVED ON THIS DEVICE"}</span><h2>{syncState === "saved" ? "Your progress is synced." : "Your progress will sync when this device is back online."}</h2><p>The original local tutor remains unchanged and private on this laptop. Its existing FSRS review history will be migrated only after an explicit import step, so nothing is overwritten.</p><strong>AI reviews and full spaced repetition are the next sync milestone.</strong></div>
    </section>
  );
}

function Settings({ syncState }: { syncState: SyncState }) {
  return (
    <section className="page narrow">
      <PageHead eyebrow="ABOUT THIS BUILD" title="Settings" text="A private hosted companion to the local Hanlu tutor." />
      <div className="settings-list">
        <article><b>Hosted curriculum</b><span>1,261 words · 12 stories · 90 grammar lessons</span></article>
        <article><b>Audio</b><span>Uses Mandarin speech available on the current device.</span></article>
        <article><b>Cloud progress</b><span>{syncState === "saved" ? "Story and grammar status sync privately across signed-in devices." : "Waiting for an internet connection before syncing."}</span></article>
        <article><b>Hosted offline access</b><span>After one successful online visit, the app shell and curriculum are cached on this device. Private progress API responses are never cached.</span></article>
        <article><b>Offline learning data</b><span>Your existing local tutor data remains on your laptop and is never uploaded automatically.</span></article>
        <article><b>Open source</b><a href="https://github.com/josecoves/hanlu-chinese-tutor" target="_blank" rel="noreferrer">View source on GitHub ↗</a></article>
      </div>
    </section>
  );
}

function storyProgressLabel(index: number, story: Story, progress?: StoryProgress) {
  if (progress?.completedAt) return `STORY ${String(index).padStart(2, "0")} · COMPLETED`;
  if (progress && progress.sentenceIndex > 0) {
    return `STORY ${String(index).padStart(2, "0")} · CONTINUE ${progress.sentenceIndex + 1} / ${story.sentences.length}`;
  }
  return `STORY ${String(index).padStart(2, "0")} · ${story.sentences.length} SENTENCES`;
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
