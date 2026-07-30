import type { Metadata } from "next";
import { HanluApp } from "./hanlu-app";
import content from "./hanlu-data.json";

export const metadata: Metadata = {
  title: "汉路 Hanlu · Chinese Tutor",
  description:
    "Learn practical Chinese through vocabulary, stories, and structured grammar.",
};

export default function Home() {
  return <HanluApp content={content} />;
}
