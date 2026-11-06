"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loading } from "@/components/ui";
import { api } from "@/lib/api";

export default function About() {
  const [md, setMd] = useState<string | null>(null);
  useEffect(() => {
    api("/meta/limitations").then((r) => setMd(r.markdown)).catch(() => setMd("Could not load limitations."));
  }, []);
  if (md === null) return <Loading />;
  return (
    <article className="card mx-auto max-w-4xl text-sm leading-relaxed [&_h1]:mb-3 [&_h1]:text-2xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_p]:my-2 [&_table]:my-3 [&_td]:border [&_td]:border-line [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-line [&_th]:bg-paper [&_th]:px-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
    </article>
  );
}
