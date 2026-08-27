import Link from "next/link";
import { requirePageSession } from "../../../server/auth-next.js";

export default async function NewRunPage() {
  await requirePageSession("/runs/new");
  return (
    <section className="empty-state-page">
      <p className="eyebrow">Operator workflow</p>
      <h1>Runs start in the guided workflow.</h1>
      <p>
        Resource identifiers are selected and validated by the portal. You do not need to type
        capsule or profile IDs manually.
      </p>
      <Link className="button" href="/workflow">Open operator workflow</Link>
    </section>
  );
}
