package util

import (
	"math/rand/v2"
	"os"
	"strconv"
)

// Rng is the source of game-setup randomness (role / profile / seat assignment). When the
// environment variable AIWOLF_SEED is set, it is seeded deterministically so the SAME seed
// reproduces the SAME role/persona/seat-order assignment — used to PAIR experimental
// conditions (game k is identical across conditions). When AIWOLF_SEED is unset it is seeded
// randomly, preserving the original (non-deterministic) behaviour.
//
// AIWOLF_SEED が設定されていれば決定的にシードし、同一シードで役職・ペルソナ・席順を再現する
// （実験の条件間ペア化に使用）。未設定なら従来どおりランダム。
var Rng = newRng()

func newRng() *rand.Rand {
	if s := os.Getenv("AIWOLF_SEED"); s != "" {
		if n, err := strconv.ParseUint(s, 10, 64); err == nil {
			return rand.New(rand.NewPCG(n+0x9e3779b97f4a7c15, n*0xbf58476d1ce4e5b9+1))
		}
	}
	return rand.New(rand.NewPCG(rand.Uint64(), rand.Uint64()))
}
