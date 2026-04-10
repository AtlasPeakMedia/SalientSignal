import Link from "next/link";

export default function Wordmark() {
  return (
    <Link href="/" className="inline-flex items-baseline gap-2 group">
      <span className="text-xl font-semibold tracking-tight text-white">
        Salient<span className="text-accent-tealBright">Signal</span>
      </span>
      <span className="text-[10px] text-text-secondary uppercase tracking-widest">
        Foreign Media Intel
      </span>
    </Link>
  );
}
