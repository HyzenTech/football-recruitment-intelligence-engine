"use strict";
const $ = id => document.getElementById(id);
const key = p => `${p.player_id}|${p.team_id}`;
const labels = {nonpenalty_xg:"Non-penalty xG",shot_linked_xg_assisted:"Shot-linked xG assisted",pass_completion_pct:"Pass completion %",carry_displacement:"Carry displacement",xg:"xG"};
const label = k => labels[k] || k.replaceAll("_", " ").replace(/^./, c => c.toUpperCase());
const number = v => v == null ? "Unavailable" : Number(v).toLocaleString("en-GB", {maximumFractionDigits:2});
const statuses = {
  INSUFFICIENT_PEERS:"Not enough complete peers for this comparison.",
  INELIGIBLE_QUERY:"This player's minutes, season coverage or positional usage do not meet peer eligibility.",
  MISSING_QUERY_FEATURES:"Required query metrics are incomplete.",
  NO_VARIABLE_FEATURES:"The complete reference population has no variable metrics.",
  CONSTANT_COMPONENT:"A required metric is constant. No priorities were redistributed.",
  NO_CANDIDATES:"No candidates meet this requirement's filters.",
  INELIGIBLE_PROFILE:"Player is outside the eligible peer population.",
  MISSING_METRIC:"Metric incomplete", MISSING_COMPONENT:"Required component incomplete",
  CONSTANT_METRIC:"No variation in peers", UNSUPPORTED_DATA:"Not supported by available data",
  DESCRIPTIVE_ONLY:"Descriptive value; no percentile"
};
let meta, players = [], manifest, contract, profileSerial = 0, comparisonProfiles = [];
const cache = new Map();

function node(tag, text, cls) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function clear(id) { $(id).replaceChildren(); return $(id); }
function message(parent, text, cls = "message") { parent.append(node("p", text, cls)); }
function card(title) { const c = node("div", null, "card"); if (title) c.append(node("h2", title)); return c; }
async function hash(bytes) {
  if (!window.crypto?.subtle) throw Error("Integrity checks require HTTPS or a loopback preview server.");
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2,"0")).join("");
}
async function fetchBytes(path) {
  const response = await fetch(path, {cache:"no-store"});
  if (!response.ok) throw Error(`Snapshot file unavailable (${response.status}). Re-export the verified data for this local preview.`);
  return response.arrayBuffer();
}
async function load(name) {
  if (cache.has(name)) return cache.get(name);
  const expected = manifest.files[name];
  if (!expected || !/^(players|metadata|ranking_examples)\.json$|^(profiles|similarity)\/[a-f0-9]{64}\.json$/.test(name)) {
    throw Error("Snapshot file is outside the verified export contract.");
  }
  const pending = (async () => {
    const bytes = await fetchBytes(`data/${name}`);
    if (bytes.byteLength !== expected.bytes || await hash(bytes) !== expected.sha256) {
      throw Error("Snapshot integrity check failed. No fallback statistics are generated.");
    }
    return JSON.parse(new TextDecoder().decode(bytes));
  })();
  cache.set(name, pending);
  try { return await pending; } catch (error) { cache.delete(name); throw error; }
}
async function getProfile(identity) {
  const path = meta.data_paths[identity]?.profile;
  if (!path) throw Error("Player is outside this snapshot.");
  return load(path);
}
function selectFill(id, rows, optional = false) {
  const select = $(id), old = select.value;
  select.replaceChildren();
  if (optional) select.append(new Option("No third player", ""));
  for (const p of rows) select.append(new Option(`${p.player_name} · ${p.team_name} (${p.primary_position_group || "mixed"})`, key(p)));
  if ([...select.options].some(o => o.value === old)) select.value = old;
}
function table(headers, rows) {
  const wrap = node("div", null, "scroll"), t = node("table"), head = node("thead"), hr = node("tr");
  for (const h of headers) { const th = node("th", h); th.scope = "col"; hr.append(th); }
  head.append(hr); t.append(head);
  const body = node("tbody");
  for (const row of rows) {
    const tr = node("tr");
    row.forEach((value, i) => {
      const td = node("td"); td.dataset.label = headers[i];
      td.append(value instanceof Node ? value : document.createTextNode(String(value)));
      tr.append(td);
    });
    body.append(tr);
  }
  t.append(body); wrap.append(t); return wrap;
}
function percentile(value, title = "Percentile") {
  const d = node("div", null, "metric-bar");
  if (value.percentile == null) { d.append(node("small", statuses[value.status] || value.status)); return d; }
  const p = node("progress"); p.max = 100; p.value = value.percentile;
  p.setAttribute("aria-label", `${title}: ${number(value.percentile)} percentile`);
  d.append(p, node("span", number(value.percentile))); return d;
}
function rawMetric(value) { return number(value.value) + (value.value != null && value.unit === "per90" ? " /90" : ""); }
function profileIdentity(p) {
  const identity = card(), heading = node("div", null, "identity"), left = node("div");
  left.append(node("h2", p.player_name), node("p", p.team_name, "subtle"));
  heading.append(left, node("span", p.peer_eligible ? "Peer eligible" : "Limited comparison coverage", "badge" + (p.peer_eligible ? "" : " warn")));
  identity.append(heading);
  const stats = node("div", null, "stats");
  for (const [name, value] of [["Validated minutes",number(p.denominator_minutes)],["Primary position",p.primary_position_group || "Mixed usage"],["Dominant share",number(p.dominant_position_share*100)+"%"],["Appearances",p.appearances]]) {
    const n = node("div", null, "stat"); n.append(node("strong",value),node("span",name)); stats.append(n);
  }
  identity.append(stats);
  if (p.partial_player_season) message(identity,"Partial player season: quarantined appearances are excluded.","unavailable");
  for (const reason of p.eligibility_reasons) identity.append(node("span",label(reason.toLowerCase()),"badge warn"));
  return identity;
}
async function explore() {
  const serial = ++profileSerial, parent = clear("profile"), identity = $("player").value;
  if (!identity) { message(parent,"No players match this filter.","empty"); return; }
  message(parent,"Loading verified player profile…");
  try {
    const p = await getProfile(identity);
    if (serial !== profileSerial) return;
    parent.replaceChildren(); parent.append(profileIdentity(p));
    const categories = card("Relative activity profiles");
    categories.append(node("p","Equal-weight category summaries; no overall player rating.","note"));
    for (const [name,v] of Object.entries(p.categories)) {
      const row = node("div",null,"category"); row.append(node("span",label(name)));
      if (v.score != null) {
        const bar = node("progress"); bar.max=100; bar.value=v.score;
        bar.setAttribute("aria-label",`${label(name)}: ${number(v.score)}`);
        row.append(bar,node("strong",number(v.score)),node("small",`${v.peer_count} complete peers · ${v.metrics.map(label).join(", ")}`));
      } else row.append(node("small",statuses[v.status] || v.status));
      categories.append(row);
    }
    parent.append(categories);
    const metrics = card("Metrics & peer percentiles");
    metrics.append(node("p","Counts and sums are per 90. Means and percentages keep their native units. Incomplete observations stay unavailable.","note"), table(
      ["Metric","Value","Percentile","Complete peers","Coverage"],
      Object.entries(p.metrics).map(([m,v])=>[label(m),rawMetric(v),percentile(v,label(m)),v.peer_count,v.coverage == null ? "No opportunities" : number(v.coverage*100)+"%"])
    ));
    parent.append(metrics);
  } catch (error) {
    if (serial === profileSerial) { parent.replaceChildren(); message(parent,error.message,"message error"); }
  }
}
function filterPlayers() {
  const q=$("search").value.toLocaleLowerCase(), role=$("role").value;
  selectFill("player",players.filter(p=>(!role || p.primary_position_group===role) && (p.player_name+" "+p.team_name).toLocaleLowerCase().includes(q)));
  explore();
}
async function action(button, output, work) {
  button.disabled=true; const parent=clear(output); parent.setAttribute("aria-busy","true");
  message(parent,"Loading verified Python results…");
  try { await work(parent); } catch(error) { parent.replaceChildren(); message(parent,error.message,"message error"); }
  finally { button.disabled=false; parent.setAttribute("aria-busy","false"); }
}
function validLimit(id) {
  const input=$(id), value=Number(input.value);
  if (!input.reportValidity() || !Number.isInteger(value) || value<1 || value>10) return null;
  return value;
}
function comparisonChart(profiles, metric) {
  const c=card(`${label(metric)} · positional percentiles`), plot=node("div",null,"comparison-chart");
  for(const p of profiles) {
    const value=p.metrics[metric], row=node("div",null,"comparison-row");
    row.append(node("strong",p.player_name),node("small",`${p.primary_position_group || "mixed"} · ${rawMetric(value)} · ${value.peer_count} complete peers`),percentile(value,`${p.player_name}, ${label(metric)}`));
    plot.append(row);
  }
  c.append(node("p","Each bar retains its own positional benchmark. Different roles are not interchangeable.","note"),plot);
  return c;
}
function renderComparison() {
  const parent=clear("comparison"), profiles=comparisonProfiles;
  if(!profiles.length) return;
  message(parent,"Each percentile uses its own position and complete metric peer population.");
  if(new Set(profiles.map(p=>p.primary_position_group)).size>1) message(parent,"Different position groups: percentile values are not a shared benchmark.","unavailable");
  parent.append(comparisonChart(profiles,$("compare-metric").value));
  const metrics=card("Metric comparison");
  metrics.append(table(["Metric",...profiles.map(p=>`${p.player_name} · ${p.primary_position_group || "mixed"}`)],Object.keys(profiles[0].metrics).map(m=>[
    label(m), ...profiles.map(p=>{const v=p.metrics[m], n=node("div"); n.append(node("strong",rawMetric(v)),node("small",v.percentile==null?(statuses[v.status]||v.status):`${number(v.percentile)} percentile · ${v.peer_count} peers`),node("small",v.coverage==null?"No opportunities":`${number(v.coverage*100)}% coverage`));return n;})
  ])));
  parent.append(metrics);
}
async function compare(parent) {
  const ids=[$("compare-a").value,$("compare-b").value,$("compare-c").value].filter(Boolean);
  comparisonProfiles=[];
  if(ids.length<2 || new Set(ids).size!==ids.length) throw Error("Choose two or three distinct player / team records.");
  comparisonProfiles=await Promise.all(ids.map(getProfile)); renderComparison();
}
async function similar(parent,k) {
  const identity=$("similar-player").value, path=meta.data_paths[identity]?.similarity;
  if(!path) throw Error("Choose a player from this snapshot.");
  const r=await load(path); parent.replaceChildren();
  if(r.status!=="AVAILABLE") {
    message(parent,statuses[r.status] || r.status,"empty");
    message(parent,`${r.peer_count} complete peers; ${r.minimum_peer_count} required.`);
    return;
  }
  message(parent,`${r.peer_count} complete peers · ${r.active_features.length} active metrics · query player excluded from every team spell.`);
  const c=card("Similar event profiles");
  c.append(table(["Player / team","Minutes","Distance","Proximity index","Closest metrics","Largest differences"],r.neighbors.slice(0,k).map(n=>[
    `${n.player_name} · ${n.team_name}`,number(n.denominator_minutes),number(n.distance),number(n.similarity_score),n.key_similarities.map(d=>label(d.metric)).join(", "),n.key_differences.map(d=>`${label(d.metric)} (${number(d.standardized_difference)} standardized)`).join(", ")
  ])));
  parent.append(c);
  for(const warning of r.warnings) message(parent,label(warning.toLowerCase()));
  for(const n of r.neighbors.slice(0,k)) {
    const detail=node("details",null,"result-detail");
    detail.append(node("summary",`${n.player_name}: metric differences`),table(["Metric","Query","Neighbor","Standardized difference","Distance share"],n.feature_differences.map(d=>[
      label(d.metric),number(d.query_value),number(d.peer_value),number(d.standardized_difference),number(d.contribution_share*100)+"%"
    ])));
    parent.append(detail);
  }
  referenceDetails(parent,r.reference_ids);
}
function referenceDetails(parent,ids) {
  const detail=node("details",null,"result-detail"), list=node("ul",null,"reference-list");
  detail.append(node("summary",`${ids.length} complete reference records`));
  for(const [player_id,team_id] of ids) {
    const p=players.find(p=>p.player_id===player_id && p.team_id===team_id);
    list.append(node("li",p?`${p.player_name} · ${p.team_name}`:`${player_id} · ${team_id}`));
  }
  detail.append(list); parent.append(detail);
}
function preset() {
  const req=meta.requirements[$("preset").value], parent=clear("weights");
  for(const [metric,weight] of Object.entries(req.weights)) {
    const c=node("div",null,"priority"); c.append(node("span",label(metric)),node("strong",number(weight)));parent.append(c);
  }
  clear("ranking");
  message($("ranking"),`${req.position_group} · minimum ${number(req.minimum_minutes)} validated minutes · fixed Python preset. Choose “Show ranked candidates” to inspect the result.`);
}
async function rank(parent,k) {
  const results=await load("ranking_examples.json"), r=results[$("preset").value];
  if(!r) throw Error("Requirement is outside the verified export.");
  parent.replaceChildren();
  message(parent,`${r.peer_count} complete reference players · normalized priorities: ${Object.entries(r.normalized_weights).map(([m,w])=>`${label(m)} ${number(w*100)}%`).join(", ")}`);
  if(r.status!=="AVAILABLE") {
    message(parent,statuses[r.status] || r.status,"empty"); referenceDetails(parent,r.reference_ids); return;
  }
  message(parent,`${r.candidate_count} eligible candidates · showing ${Math.min(k,r.rankings.length)} verified results. Scores reflect this scenario's activity priorities, not overall ability.`);
  const c=card("Ranked candidates");
  c.append(table(["Rank","Player / team","Minutes","Requirement score","Main contributions","Lower requested percentiles"],r.rankings.slice(0,k).map(n=>[
    n.rank,`${n.player_name} · ${n.team_name}`,number(n.denominator_minutes),number(n.recruitment_score),n.ranking_reasons.map(d=>`${label(d.metric)}: ${number(d.percentile)} percentile`).join("; "),n.weaker_dimensions.map(d=>`${label(d.metric)}: ${number(d.percentile)}`).join("; ")
  ])));
  parent.append(c);
  for(const n of r.rankings.slice(0,k)) {
    const detail=node("details",null,"result-detail");
    detail.append(node("summary",`${n.player_name}: score contributions`),table(["Metric","Value","Direction","Percentile","Weight","Contribution"],Object.entries(n.components).map(([m,v])=>[
      label(m),number(v.value),v.direction,number(v.percentile),number(v.normalized_weight*100)+"%",number(v.contribution)
    ])));
    parent.append(detail);
  }
  for(const warning of r.warnings) message(parent,label(warning.toLowerCase()));
  referenceDetails(parent,r.reference_ids);
  const excluded=node("details",null,"result-detail");
  excluded.append(node("summary",`${r.exclusions.length} excluded player/team records`),table(["Player / team record","Reason"],r.exclusions.map(e=>{
    const p=players.find(p=>p.player_id===e.player_id&&p.team_id===e.team_id);
    return [p?`${p.player_name} · ${p.team_name}`:`${e.player_id} · ${e.team_id}`, e.reasons.map(x=>label(x.toLowerCase())).join(", ")+(e.missing_metrics?.length?` (${e.missing_metrics.map(label).join(", ")})`:"")];
  })));
  parent.append(excluded);
}
const titles={explore:["Player Explorer","Explore validated minutes, role usage and peer-relative event profiles."],compare:["Player Comparison","Compare two or three team spells without hiding missing values or role benchmarks."],similar:["Similar Players","Inspect verified neighbors and the metrics driving their proximity."],rank:["Recruitment Search","Explore verified recruitment scenarios and every weighted contribution."]};
for(const b of document.querySelectorAll("nav button")) b.addEventListener("click",()=>{
  for(const other of document.querySelectorAll("nav button")) {
    other.classList.toggle("active",other===b);
    if(other===b) other.setAttribute("aria-current","page"); else other.removeAttribute("aria-current");
  }
  for(const view of Object.keys(titles)) $("panel-"+view).hidden=view!==b.dataset.view;
  [$("view-title").textContent,$("view-description").textContent]=titles[b.dataset.view];
});
$("search").addEventListener("input",filterPlayers);
$("role").addEventListener("change",filterPlayers);
$("player").addEventListener("change",explore);
$("compare-run").addEventListener("click",()=>action($("compare-run"),"comparison",compare));
$("compare-metric").addEventListener("change",renderComparison);
$("similar-run").addEventListener("click",()=>{const k=validLimit("similar-k");if(k!=null) action($("similar-run"),"similarity",parent=>similar(parent,k));});
$("rank-run").addEventListener("click",()=>{const k=validLimit("rank-k");if(k!=null) action($("rank-run"),"ranking",parent=>rank(parent,k));});
$("preset").addEventListener("change",preset);

async function init() {
  try {
    contract=JSON.parse(new TextDecoder().decode(await fetchBytes("snapshot-contract.json")));
    const bytes=await fetchBytes("data/manifest.json");
    if(await hash(bytes)!==contract.export_manifest_sha256) throw Error("Export manifest integrity check failed.");
    manifest=JSON.parse(new TextDecoder().decode(bytes));
    if(manifest.schema_version!=="static-demo-1.0.0" || manifest.profile_manifest_sha256!==contract.profile_manifest_sha256) throw Error("Unsupported or mismatched snapshot contract.");
    [meta,players]=await Promise.all([load("metadata.json"),load("players.json")]);
    if(!meta.full_cohort || meta.profile_manifest_sha256!==manifest.profile_manifest_sha256 || meta.ranking_mode!=="VERIFIED_PRESETS_ONLY") throw Error("Snapshot metadata does not match the frozen demo.");
    if(meta.publication_status!=="LOCAL_PREVIEW_ONLY_RIGHTS_PENDING") throw Error("Publication status requires a separately reviewed build.");
    players.sort((a,b)=>a.player_name.localeCompare(b.player_name)||a.team_name.localeCompare(b.team_name));
    $("cohort").textContent=`WSL · ${meta.season} · verified V1`;
    const coverage=clear("coverage");
    coverage.append(node("p",`${meta.unique_players} players · ${meta.profile_count} team spells · ${meta.eligible_profiles} peer eligible`),node("p",`At least ${meta.minimum_minutes} validated minutes, 60% dominant positional exposure and ${meta.minimum_peers} complete peers. Minutes include stoppage time.`),node("p","One historical league. Expert/scout and predictive validation pending."),node("small",`Provider revision: ${meta.source_revision}`),node("small",`Profile manifest: ${meta.profile_manifest_sha256}`));
    for(const role of meta.roles) $("role").append(new Option(role,role));
    for(const name of Object.keys(meta.requirements)) $("preset").append(new Option(meta.requirements[name].name,name));
    for(const id of ["player","compare-a","compare-b","similar-player"]) selectFill(id,players);
    selectFill("compare-c",players,true);
    const eligible=players.filter(p=>p.peer_eligible&&p.primary_position_group==="CB").sort((a,b)=>b.denominator_minutes-a.denominator_minutes);
    for(const id of ["player","compare-a","similar-player"]) $(id).value=key(eligible[0]);
    $("compare-b").value=key(eligible[1]);
    $("preset").value="CB_defensive_activity";
    const initial=await getProfile($("player").value);
    for(const metric of Object.keys(initial.metrics)) $("compare-metric").append(new Option(label(metric),metric));
    $("compare-metric").value="interceptions";
    preset(); $("workspace-controls").inert=false;
    await explore();
  } catch(error) {
    $("cohort").textContent="Snapshot unavailable";
    $("global-error").hidden=false;
    $("global-error").textContent=`Unable to load verified snapshot: ${error.message}`;
    clear("profile"); message($("profile"),"No fallback player statistics are generated.","empty");
    $("workspace-controls").inert=true;
    for(const control of document.querySelectorAll("#workspace-controls input, #workspace-controls select, #workspace-controls button")) control.disabled=true;
  }
}
init();
