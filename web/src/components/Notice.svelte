<script>
  // The two notices the brief requires to be prominent on every page.
  export let compact = false;
</script>

<div class="notice" class:compact role="note" aria-label="Important limitations">
  <strong>Research and education only.</strong>
  <span>Not an emergency alert, evacuation routing, or fire-risk service — and not for
    emergency decision-making. For current alerts, use
    <a href="https://www.mauicounty.gov/983/MEMA-Alerts" target="_blank" rel="noopener noreferrer">MEMA Alerts</a>.</span>
</div>

<style>
  .notice {
    display: flex; flex-wrap: wrap; gap: .25em .6em; align-items: baseline;
    background: #1f1a12; border: 1px solid #4a3b22; border-left: 4px solid var(--amber);
    color: #e8d3b0; padding: .7em 1em; border-radius: 2px; font-size: .92rem;
  }
  .notice a { color: #6b3d06; font-weight: 600; }
  .compact { padding: .45em .8em; font-size: .82rem; }
</style>
