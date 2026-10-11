import { login, signup } from "./api/api.js";
import { ApiError } from "./api/errors.js";

const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,20}$/;
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 64;

export function validateSignup(username, password) {
  if (!USERNAME_PATTERN.test(username)) {
    return "아이디는 3~20자 영문, 숫자, 밑줄만 사용할 수 있습니다.";
  }

  if (password.length < PASSWORD_MIN_LENGTH || password.length > PASSWORD_MAX_LENGTH) {
    return "비밀번호는 8~64자를 입력해 주세요.";
  }

  return null;
}

export function validateLogin(username, password) {
  if (!username || !password) {
    return "아이디와 비밀번호를 모두 입력해 주세요.";
  }

  return null;
}

export function getAuthErrorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  return "네트워크 오류가 발생했습니다. 연결을 확인한 뒤 다시 시도해 주세요.";
}

/**
 * 인증 폼의 DOM과 로컬 요청 상태만 관리한다. 로그인 이후 화면 전환은 상위 모듈이 맡는다.
 */
export function initializeAuth({ onLoginSuccess = () => {}, onLogout = () => {}, authApi = { signup, login } } = {}) {
  const loginForm = document.querySelector("#login-form");
  const signupForm = document.querySelector("#signup-form");
  const messageElement = document.querySelector("#auth-message");
  const titleElement = document.querySelector("#auth-title");
  const loginUsername = document.querySelector("#login-username");
  const loginPassword = document.querySelector("#login-password");
  const signupUsername = document.querySelector("#signup-username");
  const signupPassword = document.querySelector("#signup-password");
  const loginButton = document.querySelector("#login-submit");
  const signupButton = document.querySelector("#signup-submit");
  const viewButtons = document.querySelectorAll("[data-auth-view]");
  const logoutButton = document.querySelector("#logout-button");
  const logoutMessage = document.querySelector("#logout-message");

  if (
    !loginForm ||
    !signupForm ||
    !messageElement ||
    !titleElement ||
    !loginUsername ||
    !loginPassword ||
    !signupUsername ||
    !signupPassword ||
    !loginButton ||
    !signupButton
  ) {
    return;
  }

  let loginPending = false;
  let signupPending = false;

  function setMessage(message, state = "") {
    messageElement.textContent = message;
    messageElement.dataset.state = state;
  }

  function showView(view) {
    const isLogin = view === "login";
    loginForm.hidden = !isLogin;
    signupForm.hidden = isLogin;
    titleElement.textContent = isLogin ? "로그인" : "회원가입";
    setMessage("");
  }

  viewButtons.forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.authView));
  });

  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (signupPending) {
      return;
    }

    const validationMessage = validateSignup(signupUsername.value, signupPassword.value);
    if (validationMessage) {
      setMessage(validationMessage, "error");
      return;
    }

    signupPending = true;
    signupButton.disabled = true;
    setMessage("회원가입 요청을 보내는 중입니다.");
    try {
      const user = await authApi.signup(signupUsername.value, signupPassword.value);
      loginUsername.value = user.username;
      loginPassword.value = "";
      signupForm.reset();
      showView("login");
      setMessage("회원가입이 완료되었습니다. 로그인해 주세요.", "success");
    } catch (error) {
      setMessage(getAuthErrorMessage(error), "error");
    } finally {
      signupPending = false;
      signupButton.disabled = false;
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (loginPending) {
      return;
    }

    const validationMessage = validateLogin(loginUsername.value, loginPassword.value);
    if (validationMessage) {
      setMessage(validationMessage, "error");
      return;
    }

    loginPending = true;
    loginButton.disabled = true;
    setMessage("로그인 요청을 보내는 중입니다.");
    try {
      await authApi.login(loginUsername.value, loginPassword.value);
      loginPassword.value = "";
      setMessage("로그인되었습니다.", "success");
      onLoginSuccess();
    } catch (error) {
      setMessage(getAuthErrorMessage(error), "error");
    } finally {
      loginPending = false;
      loginButton.disabled = false;
    }
  });

  if (logoutButton && logoutMessage) {
    let logoutPending = false;
    logoutButton.addEventListener("click", async () => {
      if (logoutPending) {
        return;
      }

      logoutPending = true;
      logoutButton.disabled = true;
      logoutMessage.textContent = "로그아웃 요청을 보내는 중입니다.";
      try {
        await onLogout();
      } catch (error) {
        logoutMessage.textContent = getAuthErrorMessage(error);
      } finally {
        logoutPending = false;
        logoutButton.disabled = false;
      }
    });
  }

  return { showLogin: () => showView("login"), showSignup: () => showView("signup") };
}
