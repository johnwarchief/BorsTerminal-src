// features/master/ui/SynthesisBox.tsx -- باکس «تحلیل داوری مستر»
// متن synthesis قانون‌محور از همان state داوری — نه LLM.
export function SynthesisBox({ text }: { text: string }) {
  return (
    <div className="glass-panel panel-in p-4" role="article" aria-label="تحلیل داوری مستر">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-black text-text-primary">
        <span className="inline-block h-2 w-2 rounded-full bg-neon-cyan shadow-[0_0_8px_var(--neon-cyan)]" aria-hidden />
        تحلیل داوری مستر
      </h3>
      <p className="break-words text-xs leading-6 text-text-secondary">{text}</p>
    </div>
  );
}
