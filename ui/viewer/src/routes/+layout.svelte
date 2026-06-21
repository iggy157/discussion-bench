<script lang="ts">
  // INLG: top navigation switching between the two environments.
  // 上部ナビ: 人狼(AIWolf) と HiddenBench をページごと切り替える。
  import { base } from "$app/paths";
  import "../app.css";

  let { children } = $props();
</script>

<div class="navbar bg-base-300 min-h-0 gap-2 px-3 py-1 text-sm">
  <a href="{base}/" class="mr-1 font-bold">INLG</a>
  <a href="{base}/demo" class="btn btn-xs btn-ghost">AIWolf</a>
  <a href="{base}/hidden-bench" class="btn btn-xs btn-ghost">HiddenBench</a>
</div>

{@render children()}
