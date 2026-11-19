import { expect, test } from "bun:test"
import { parseStep } from "./step"

test("a step is provider/model#variant; #default and an empty variant mean none", () => {
  expect(parseStep("anthropic/claude-opus-5-5#high")).toEqual({
    providerID: "anthropic",
    id: "claude-opus-5-5",
    variant: "high",
  })
  expect(parseStep("openai/gpt-6.1-sol")).toEqual({
    providerID: "openai",
    id: "gpt-6.1-sol",
  })
  expect(parseStep("openai/gpt-6.1-sol#default")).toEqual({
    providerID: "openai",
    id: "gpt-6.1-sol",
  })
  expect(parseStep("openai/gpt-6.1-sol#")).toEqual({
    providerID: "openai",
    id: "gpt-6.1-sol",
  })
})

test("the provider ends at the first slash and the variant at the last hash", () => {
  expect(parseStep("openrouter/anthropic/claude#a#b")).toEqual({
    providerID: "openrouter",
    id: "anthropic/claude#a",
    variant: "b",
  })
})

test("text without a provider or a model names no step", () => {
  for (const step of ["", "nonsense", "/model", "provider/", "provider/#high"])
    expect(parseStep(step)).toBeUndefined()
})
