import ContextInspectorClient from "./context-inspector-client";
import { requirePageSession } from "../../../server/auth-next.js";

export default async function ContextInspectorPage({ params }) {
  const { capsuleId } = await params;
  await requirePageSession(`/context-inspector/${encodeURIComponent(capsuleId)}`);
  return <ContextInspectorClient capsuleId={capsuleId} />;
}
