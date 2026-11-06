"use client";

export type Message = {
  channel: string;
  language: string;
  rtl: boolean;
  text: string;
  english_gloss: string;
  send_at?: string;
  review_status?: string;
  to?: string;
  timing_notes?: string[];
};

const CHANNEL: Record<string, string> = { whatsapp: "WhatsApp", sms: "SMS", call_script: "Call script", chw_script: "Community health worker script" };

export default function Phone({ m, showGloss = true }: { m: Message; showGloss?: boolean }) {
  const script = m.channel === "call_script" || m.channel === "chw_script";
  return (
    <div className="mx-auto w-full max-w-sm rounded-[1.6rem] border-[6px] border-ink bg-[#ECE5DD] p-3 shadow-sm" data-testid="phone">
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <span className="font-semibold text-ink">{CHANNEL[m.channel] ?? m.channel}{m.to ? ` · to ${m.to}` : ""}</span>
        <span>{m.send_at?.replace("T", " ")}</span>
      </div>
      <div
        lang={m.language}
        dir={m.rtl ? "rtl" : "ltr"}
        data-testid="message-text"
        className={`whitespace-pre-wrap rounded-lg p-3 text-[15px] leading-relaxed shadow-sm ${script ? "bg-white font-mono text-[13px]" : m.channel === "sms" ? "bg-white" : "bg-[#DCF8C6]"}`}
      >
        {m.text}
      </div>
      {m.review_status === "machine_draft" && (
        <p className="mt-2 text-xs text-coral">Machine-drafted translation: needs native-speaker review before use.</p>
      )}
      {showGloss && m.language !== "en" && (
        <details className="mt-2 rounded bg-white/70 p-2 text-xs" open>
          <summary className="cursor-pointer font-semibold">English gloss</summary>
          <p lang="en" className="mt-1">{m.english_gloss}</p>
        </details>
      )}
      {m.timing_notes && m.timing_notes.length > 0 && (
        <p className="mt-2 text-xs text-muted">Send time moved: {m.timing_notes.join("; ")}</p>
      )}
    </div>
  );
}
