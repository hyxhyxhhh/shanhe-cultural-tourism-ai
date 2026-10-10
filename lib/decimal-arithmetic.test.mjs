import test from "node:test";
import assert from "node:assert/strict";
import { decimalSum, decimalMultiply } from "./decimal-arithmetic.ts";
test("budget arithmetic preserves decimal numeric contract", () => {
  assert.equal(decimalMultiply(3, 0.1), 0.3);
  assert.equal(decimalSum([0.1, 0.2]), 0.3);
  assert.equal(decimalSum([1e-7, 2e-7]), 3e-7);
  assert.equal(decimalMultiply(1e-7, 3), 3e-7);
  assert.equal(decimalSum([1e20, -1e20, 0.1]), 0.1);
  assert.throws(() => decimalSum([Infinity]));
});
