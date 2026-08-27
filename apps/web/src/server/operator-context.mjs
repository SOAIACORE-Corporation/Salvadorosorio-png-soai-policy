import { AsyncLocalStorage } from "node:async_hooks";

const operatorStorage = new AsyncLocalStorage();

export function withOperatorContext(operator, callback) {
  return operatorStorage.run(operator, callback);
}

export function currentOperatorContext() {
  return operatorStorage.getStore() ?? null;
}
