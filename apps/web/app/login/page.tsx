import Link from "next/link";
import { copy } from "@/lib/copy.ko";

export default function Login() {
  return (
    <main className="page">
      <div className="topbar">
        <Link href="/home">←</Link>
      </div>
      <section className="section" style={{ textAlign: "center", padding: "32px 18px" }}>
        <h2>{copy.loginPage.title}</h2>
        <p className="sub">{copy.loginPage.body}</p>
      </section>
    </main>
  );
}
