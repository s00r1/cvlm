// Loader animation à l’envoi du formulaire
document.getElementById('mainForm').addEventListener('submit', function() {
    document.getElementById('loader-overlay').style.display = 'flex';
});
// Affiche le nom du fichier uploadé + bouton "×"
document.getElementById('cv_file').addEventListener('change', function(e){
    let info = document.getElementById('uploadedFileName');
    info.innerHTML = "";
    if(this.files.length > 0){
        info.style.display = "inline-flex";
        let span = document.createElement("span");
        span.textContent = "Fichier sélectionné : " + this.files[0].name;
        info.appendChild(span);

        let btn = document.createElement("button");
        btn.type = "button";
        btn.innerHTML = "&times;";
        btn.className = "remove-file-btn";
        btn.title = "Retirer le fichier";
        btn.onclick = function() {
            document.getElementById('cv_file').value = "";
            info.style.display = "none";
            info.innerHTML = "";
        };
        info.appendChild(btn);
    } else {
        info.style.display = "none";
        info.innerHTML = "";
    }
});
// Show/hide manual CV section
const showManualBtn = document.getElementById('showManualBtn');
const manualSection = document.getElementById('manualSection');
let visible = false;
showManualBtn.addEventListener('click', function() {
    visible = !visible;
    manualSection.style.display = visible ? "block" : "none";
    showManualBtn.querySelector('.plusicon').textContent = visible ? "−" : "+";
    showManualBtn.querySelector('span').style.background = visible ? "#dde2fa" : "#edf0ff";
});
// Add/remove XP rows
function addXp() {
    const div = document.createElement('div');
    div.className = 'field-row xp-row';
    div.innerHTML = `
        <div><input type="text" name="xp_poste" placeholder="Poste occupé"></div>
        <div><input type="text" name="xp_entreprise" placeholder="Entreprise"></div>
        <div><input type="text" name="xp_lieu" placeholder="Lieu"></div>
        <div><input type="text" name="xp_debut" placeholder="Début (AAAA-MM)"></div>
        <div><input type="text" name="xp_fin" placeholder="Fin (AAAA-MM ou actuel)"></div>
        <button type="button" class="suppr-btn" onclick="this.parentNode.remove()">×</button>
    `;
    document.getElementById('xpList').appendChild(div);
}
function addDip() {
    const div = document.createElement('div');
    div.className = 'field-row dip-row';
    div.innerHTML = `
        <div><input type="text" name="dip_titre" placeholder="Intitulé du diplôme"></div>
        <div><input type="text" name="dip_lieu" placeholder="Lieu d'obtention"></div>
        <div><input type="text" name="dip_date" placeholder="Date (AAAA)"></div>
        <button type="button" class="suppr-btn" onclick="this.parentNode.remove()">×</button>
    `;
    document.getElementById('dipList').appendChild(div);
}
// Theme switch
if (
    (localStorage.getItem("theme") === "dark") ||
    (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches && !localStorage.getItem("theme"))
) {
    document.body.classList.add("dark-mode");
    document.getElementById('themeSwitcher').textContent = "☀️";
}
document.getElementById('themeSwitcher').addEventListener('click', function () {
    document.body.classList.toggle('dark-mode');
    if(document.body.classList.contains('dark-mode')) {
        this.textContent = "☀️";
        localStorage.setItem("theme", "dark");
    } else {
        this.textContent = "🌘";
        localStorage.setItem("theme", "light");
    }
});

// Toggle photo upload depending on template choice
const templateSelect = document.getElementById('templateSelect');
const photoZone = document.getElementById('photoZone');
function togglePhotoZone() {
    if (!templateSelect || !photoZone) return;
    photoZone.style.display = templateSelect.value === 'premium' ? 'block' : 'none';
}
if (templateSelect) {
    templateSelect.addEventListener('change', togglePhotoZone);
    togglePhotoZone();
}
