"use client";

import { useMemo, useState } from "react";

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
type Tab =
  | "Today"
  | "Vocabulary"
  | "Topics"
  | "Stories"
  | "Grammar"
  | "Progress"
  | "Settings";

const tabs: Tab[] = [
  "Today",
  "Vocabulary",
  "Topics",
  "Stories",
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
    setSentenceIndex(0);
    setShowPinyin(true);
    setShowTranslation(false);
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
            setSentenceIndex={setSentenceIndex}
            openStory={openStory}
            closeStory={() => setStoryId(null)}
            showPinyin={showPinyin}
            setShowPinyin={setShowPinyin}
            showTranslation={showTranslation}
            setShowTranslation={setShowTranslation}
          />
        )}
        {tab === "Grammar" && (
          <GrammarLibrary
            lessons={content.grammar}
            selectedId={grammarId}
            setSelectedId={setGrammarId}
          />
        )}
        {tab === "Progress" && <Progress />}
        {tab === "Settings" && <Settings />}
      </main>

      <footer>
        <span>汉路 hosted beta · public curriculum preview</span>
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
          <button onClick={() => onTab("Topics")}><b>03</b><strong>Build useful vocabulary</strong><span>Browse HSK 1–2 words by everyday theme.</span></button>
        </div>
      </section>
    </>
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
}) {
  const story = stories.find((item) => item.id === storyId);
  if (!story) {
    return (
      <section className="page">
        <PageHead eyebrow="READING LIBRARY" title="Stories" text="Short original stories designed for HSK 1–2 learners." />
        <div className="story-grid">
          {stories.map((item, index) => (
            <button key={item.id} onClick={() => openStory(item.id)}>
              <span>STORY {String(index + 1).padStart(2, "0")} · 8 SENTENCES</span>
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
}: {
  lessons: Grammar[];
  selectedId: number | null;
  setSelectedId: (id: number | null) => void;
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
            <span>LESSON {String(index + 1).padStart(2, "0")}</span>{lesson.recommendedEarly && <b className="recommended-chip">◆ Recommended early</b>}<strong>{lesson.titleEn}</strong><em>{lesson.titleZh}</em><code>{lesson.pattern}</code>
          </button>
        ))}
      </div>
    </section>
  );
}

function Progress() {
  return (
    <section className="page narrow">
      <PageHead eyebrow="HOSTED BETA" title="Progress" text="Your existing progress remains private and safe in the offline app." />
      <div className="notice-card"><span>COMING NEXT</span><h2>Personal accounts and synced learning progress</h2><p>The first hosted release focuses on making the complete curriculum available online. Account-based review history, story completion, and grammar mastery will be added before public learning data is enabled.</p><strong>No visitor shares another person’s progress.</strong></div>
    </section>
  );
}

function Settings() {
  return (
    <section className="page narrow">
      <PageHead eyebrow="ABOUT THIS BUILD" title="Settings" text="The hosted beta and offline tutor are intentionally separate for now." />
      <div className="settings-list">
        <article><b>Hosted curriculum</b><span>1,261 words · 12 stories · 90 grammar lessons</span></article>
        <article><b>Audio</b><span>Uses Mandarin speech available on the current device.</span></article>
        <article><b>Offline learning data</b><span>Remains on your laptop and is never uploaded.</span></article>
        <article><b>Open source</b><a href="https://github.com/josecoves/hanlu-chinese-tutor" target="_blank" rel="noreferrer">View source on GitHub ↗</a></article>
      </div>
    </section>
  );
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
