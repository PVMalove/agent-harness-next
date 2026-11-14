/* Site preferences for the existing Archify viewer; authored diagrams stay intact. */
(function () {
  if (!window.Archify || !Archify.motionGovernor) return;
  // Use the viewer's own reduced-motion, visibility and interaction safeguards.
  // Do not persist a site default as the reader's preference on other viewers.
  Archify.motionGovernor.setMode("live", { persist: false });
  var motion = document.getElementById("btn-motion");
  if (motion) {
    motion.hidden = true;
    motion.tabIndex = -1;
  }
})();
