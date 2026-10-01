"""Deprecated compatibility API. PCA must never determine quote-price weights."""

def all_weights():
    return {"gpu": ({k: .25 for k in ["aws", "lambda", "coreweave", "azure"]}, "fixed"),
            "api": ({k: 1/3 for k in ["openai", "anthropic", "google"]}, "fixed"),
            "power": ({k: .2 for k in ["CA", "IA", "OR", "TX", "VA"]}, "context_only"),
            "market": ({}, "context_only")}
