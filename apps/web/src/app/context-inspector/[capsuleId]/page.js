import ContextInspectorClient from "./context-inspector-client";

export default async function ContextInspectorPage({ params }) {
  const { capsuleId } = await params;
  return <ContextInspectorClient capsuleId={capsuleId} />;
}
