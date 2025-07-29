document.addEventListener('DOMContentLoaded', () => {
  // 1) Eye-icon toggle for both Password & Confirm Password
  document.querySelectorAll('.password-toggle i').forEach(toggle => {
    const input = toggle.closest('.form-group').querySelector('input');
    toggle.addEventListener('click', () => {
      const isPwd = input.type === 'password';
      input.type = isPwd ? 'text' : 'password';
      toggle.classList.replace(
        isPwd ? 'fa-eye' : 'fa-eye-slash',
        isPwd ? 'fa-eye-slash' : 'fa-eye'
      );
    });
  });

  // 2) Dismiss any flash-style alerts
  document.body.addEventListener('click', e => {
    if (e.target.matches('.alert-close')) {
      const box = e.target.closest('.auth-alert');
      box.classList.remove('alert-show');
      setTimeout(() => box.remove(), 300);
    }
  });

  // 3) Strong-password generator popup
  const pwGroup       = document.querySelector('.password-group');
  const pwGenToggle   = document.getElementById('pwGenToggle');
  const pwPopup       = document.getElementById('pwPopup');
  const pwPopupClose  = document.getElementById('pwPopupClose');
  const pwLength      = document.getElementById('pwLength');
  const pwLengthVal   = document.getElementById('pwLengthValue');
  const genBtn        = document.getElementById('genBtn');
  const pwOutput      = document.getElementById('pwOutputPopup');
  const copyBtn       = document.getElementById('copyPwBtn');
  const pwdField      = document.getElementById('password');
  const confirmField  = document.getElementById('confirm_password');
  const usernameFld   = document.getElementById('name');
  const emailFld      = document.getElementById('email');

  // crypto-secure random integer < max
  function randInt(max) {
    const a = new Uint32Array(1);
    window.crypto.getRandomValues(a);
    return a[0] % max;
  }

  // generate one password candidate
  function generatePassword() {
    const length = +pwLength.value;
    pwLengthVal.textContent = length;
    if (length < 8) return;

    const lower = 'abcdefghijklmnopqrstuvwxyz';
    const upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const nums  = '0123456789';
    const syms  = '!@#$%^&*()_+[]{}|;:,.<>?';
    const all   = lower + upper + nums + syms;

    // seed one of each category
    let chars = [
      lower[randInt(lower.length)],
      upper[randInt(upper.length)],
      nums[randInt(nums.length)],
      syms[randInt(syms.length)]
    ];
    // fill remaining
    while (chars.length < length) {
      chars.push(all[randInt(all.length)]);
    }
    // Fisher–Yates shuffle
    for (let i = chars.length - 1; i > 0; i--) {
      const j = randInt(i + 1);
      [chars[i], chars[j]] = [chars[j], chars[i]];
    }
    const pwd = chars.join('');

    // reject three identical in a row
    if (/(\S)\1\1/.test(pwd)) return generatePassword();

    // reject if containing username or email prefix
    const uname = usernameFld.value.trim().toLowerCase();
    const mail  = emailFld.value.trim().toLowerCase().split('@')[0];
    if ((uname && pwd.toLowerCase().includes(uname)) ||
        (mail  && pwd.toLowerCase().includes(mail)))
      return generatePassword();

    pwOutput.value = pwd;
  }

  // open popup
  pwGenToggle.addEventListener('click', e => {
    e.stopPropagation();
    pwGroup.classList.toggle('show');
    if (pwGroup.classList.contains('show')) generatePassword();
  });
  // close via ×
  pwPopupClose.addEventListener('click', () =>
    pwGroup.classList.remove('show')
  );
  // click outside → close
  document.addEventListener('click', e => {
    if (!e.target.closest('.password-group')) {
      pwGroup.classList.remove('show');
    }
  });

  // slider & generate button
  pwLength.addEventListener('input', generatePassword);
  genBtn.addEventListener('click', generatePassword);

  // copy generated into both fields
  copyBtn.addEventListener('click', () => {
    const p = pwOutput.value;
    if (!p) return;
    pwdField.value      = p;
    confirmField.value  = p;
    pwGroup.classList.remove('show');
  });
});
