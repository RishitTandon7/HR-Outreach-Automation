const dialog = document.querySelector('#composer');
document.querySelector('#createCampaign').addEventListener('click', () => dialog.showModal());
document.querySelector('.close').addEventListener('click', () => dialog.close());
document.querySelector('#continue').addEventListener('click', () => {
  const name = dialog.querySelector('input').value.trim();
  if (name) {
    document.querySelector('.subhead').textContent = `“${name}” is ready for its finishing touches.`;
  }
});
document.querySelectorAll('.nav-link').forEach(link => link.addEventListener('click', () => {
  document.querySelectorAll('.nav-link').forEach(item => item.classList.remove('active'));
  link.classList.add('active');
}));
