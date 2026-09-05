// Copyright 2026 Costel Iordan (costel.iordan@gmail.com)
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/* assets/theme.js — offline theme toggle for the HTML guides.
   Reads localStorage.theme ("light"|"dark"), falls back to
   prefers-color-scheme; sets html[data-theme] and injects a toggle
   button into the guide header (PART-01 §C). No network, no build step. */
(function () {
    var root = document.documentElement;
    var stored = null;
    try { stored = localStorage.getItem("theme"); } catch (e) {}
    if (stored !== "light" && stored !== "dark" && !root.getAttribute("data-theme")) {
        var dark = window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;
        root.setAttribute("data-theme", dark ? "dark" : "light");
    }
    var header = document.querySelector("header");
    if (!header) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.setAttribute("aria-label", "Toggle light/dark theme");
    var label = function () {
        btn.textContent = root.getAttribute("data-theme") === "dark"
            ? "Light mode" : "Dark mode";
    };
    btn.addEventListener("click", function () {
        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem("theme", next); } catch (e) {}
        label();
    });
    label();
    header.appendChild(btn);
})();
