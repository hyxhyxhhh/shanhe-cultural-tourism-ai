type DecimalParts = { coefficient: bigint; exponent: number };
function parts(value: number): DecimalParts {
  if (!Number.isFinite(value)) throw new Error("Decimal arithmetic requires finite numbers");
  const [mantissa, exponent = "0"] = String(value).toLowerCase().split("e");
  const fractionLength = mantissa.split(".")[1]?.length ?? 0;
  return { coefficient: BigInt(mantissa.replace(".", "")), exponent: Number(exponent) - fractionLength };
}
function number(value: DecimalParts): number {
  const result = Number(`${value.coefficient}e${value.exponent}`);
  if (!Number.isFinite(result)) throw new Error("Decimal result exceeds supported numeric range");
  return result;
}
export function decimalMultiply(left: number, right: number): number {
  const a = parts(left), b = parts(right);
  return number({ coefficient: a.coefficient * b.coefficient, exponent: a.exponent + b.exponent });
}
export function decimalSum(values: number[]): number {
  if (!values.length) return 0;
  const decimals = values.map(parts);
  const exponent = Math.min(...decimals.map((value) => value.exponent));
  return number({ coefficient: decimals.reduce((total, value) => total + value.coefficient * BigInt(10) ** BigInt(value.exponent - exponent), BigInt(0)), exponent });
}
