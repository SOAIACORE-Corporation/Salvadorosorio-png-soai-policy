import RunsHistoryClient from "./runs-history-client";
import { requirePageSession } from "../../server/auth-next.js";

export default async function RunsHistoryPage() {
  await requirePageSession("/runs");
  return <RunsHistoryClient />;
}
