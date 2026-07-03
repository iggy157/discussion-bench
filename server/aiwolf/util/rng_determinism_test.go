package util

import (
	"fmt"
	"math/rand/v2"
	"testing"

	"github.com/aiwolfdial/aiwolf-nlp-server/model"
)

func roleOrder(seed uint64) []string {
	Rng = rand.New(rand.NewPCG(seed+0x9e3779b97f4a7c15, seed*0xbf58476d1ce4e5b9+1))
	roles := map[model.Role]int{model.R_VILLAGER: 2, model.R_WEREWOLF: 1, model.R_SEER: 1, model.R_POSSESSED: 1}
	rl := expandRolesSorted(roles)
	Rng.Shuffle(len(rl), func(i, j int) { rl[i], rl[j] = rl[j], rl[i] })
	o := make([]string, len(rl))
	for i, r := range rl {
		o[i] = r.Name
	}
	return o
}

func TestSeedDeterministic(t *testing.T) {
	a, b := roleOrder(5), roleOrder(5)
	if fmt.Sprint(a) != fmt.Sprint(b) {
		t.Fatalf("seed 5 NOT reproducible: %v vs %v", a, b)
	}
	t.Logf("seed5=%v  seed6=%v  seed7=%v", a, roleOrder(6), roleOrder(7))
}
