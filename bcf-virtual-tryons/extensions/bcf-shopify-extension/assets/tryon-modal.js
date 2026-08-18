(function () {
  var BCF_BACKEND_URL = "https://server.becausefuture.tech";
  var BCF_GUEST_EMAIL = "guest@bcf.com";
  var BCF_GUEST_PASSWORD = "bcf123";

  function bcfLogin(email, password) {
    return fetch(BCF_BACKEND_URL + "/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password })
    }).then(function (response) {
      return response.json().then(function (result) {
        if (!response.ok || !result.success) {
          throw new Error(result.error || "Login failed");
        }
        return result.data;
      });
    });
  }

  function bcfGuestLogin() {
    return bcfLogin(BCF_GUEST_EMAIL, BCF_GUEST_PASSWORD);
  }

  function bcfUrlToFile(url, filename) {
    return fetch(url).then(function (response) {
      return response.blob();
    }).then(function (blob) {
      return new File([blob], filename, { type: blob.type || "image/png" });
    });
  }

  function bcfAuthHeaders(token) {
    return token ? { "Authorization": "Bearer " + token } : {};
  }

  function bcfTryOnGemini(token, avatarFile, garmentFile) {
    var formData = new FormData();
    if (avatarFile) formData.append("avatar_image", avatarFile);
    if (garmentFile) formData.append("garment_image", garmentFile);

    return fetch(BCF_BACKEND_URL + "/api/tryon-gemini", {
      method: "POST",
      headers: bcfAuthHeaders(token),
      body: formData
    }).then(function (response) {
      if (!response.ok) {
        return response.json().then(function (result) {
          throw new Error(result.error || "Try-on failed");
        });
      }
      return response.blob().then(function (blob) {
        return URL.createObjectURL(blob);
      });
    });
  }

  function toggleHidden(el, shouldHide) {
    if (!el) return;
    el.classList.toggle("bcf-hidden", shouldHide);
  }

  function showError(el, message) {
    if (!el) {
      console.error(message);
      return;
    }
    el.textContent = message;
    toggleHidden(el, false);
  }

  function initializeTryOnRoot(root) {
    if (!root || root.dataset.tryonInitialized === "true") return;
    root.dataset.tryonInitialized = "true";

    var openButton = root.querySelector('[data-tryon-open]');
    var overlay = root.querySelector('[data-tryon-overlay]');
    var closeButton = root.querySelector('[data-tryon-close]');
    var loginView = root.querySelector('[data-tryon-view="login"]');
    var homeView = root.querySelector('[data-tryon-view="home"]');
    var profileView = root.querySelector('[data-tryon-view="profile"]');
    var avatarSwitch = root.querySelector('[data-tryon-avatar-switch]');
    var nav = root.querySelector('[data-tryon-nav]');
    var navButtons = root.querySelectorAll('.bcf-nav-btn[data-view]');
    var signInButton = root.querySelector('[data-tryon-signin]');
    var guestButton = root.querySelector('[data-tryon-guest]');
    var emailInput = root.querySelector('[data-tryon-email]');
    var passwordInput = root.querySelector('[data-tryon-password]');
    var loginError = root.querySelector('[data-tryon-login-error]');
    var uploadInput = root.querySelector('[data-tryon-upload-input]');
    var uploadTrigger = root.querySelector('[data-upload-trigger="true"]');
    var avatarButtons = root.querySelectorAll('[data-tryon-avatar-btn][data-avatar-url]');
    var avatarPreviewImages = root.querySelectorAll('[data-tryon-avatar-preview]');
    var avatarStage = root.querySelector('[data-tryon-avatar-stage]');
    var tryOnButton = root.querySelector('[data-tryon-run]');
    var loadingWrap = root.querySelector('[data-tryon-loading]');
    var resultWrap = root.querySelector('[data-tryon-result]');
    var resultImage = root.querySelector('[data-tryon-result-image]');
    var homeError = root.querySelector('[data-tryon-home-error]');
    var tryAgainButton = root.querySelector('[data-tryon-reset]');
    var profileSession = root.querySelector('[data-profile-session]');
    var profileEmail = root.querySelector('[data-profile-email]');

    var garmentImageUrl = root.getAttribute("data-tryon-garment-image") || "";

    var state = {
      loggedIn: false,
      sessionType: "guest",
      email: "guest@example.com",
      token: null,
      user: null,
      currentView: "login",
      selectedAvatar: root.getAttribute("data-default-avatar") || "",
      selectedAvatarFile: null,
      busy: false,
      homeSurface: "avatar"
    };

    function setHomeSurface(surface) {
      state.homeSurface = surface;
      toggleHidden(avatarStage, surface !== "avatar");
      toggleHidden(loadingWrap, surface !== "loading");
      toggleHidden(resultWrap, surface !== "result");
    }

    function updateNavActive(view) {
      navButtons.forEach(function (btn) {
        btn.classList.toggle("is-active", btn.getAttribute("data-view") === view);
      });
    }

    function render() {
      var view = state.loggedIn ? state.currentView : "login";

      toggleHidden(loginView, view !== "login");
      toggleHidden(homeView, view !== "home");
      toggleHidden(profileView, view !== "profile");
      toggleHidden(nav, !state.loggedIn);
      toggleHidden(avatarSwitch, !(state.loggedIn && view === "home"));

      if (profileSession) {
        profileSession.textContent = state.sessionType === "signed_in" ? "Signed in" : "Guest";
      }
      if (profileEmail) {
        profileEmail.textContent = state.email;
      }

      avatarPreviewImages.forEach(function (img) {
        img.src = state.selectedAvatar;
      });

      if (view === "home") {
        setHomeSurface(state.homeSurface);
      }

      updateNavActive(view);
    }

    function openModal() {
      toggleHidden(overlay, false);
      overlay.setAttribute("aria-hidden", "false");
      render();
    }

    function closeModal() {
      toggleHidden(overlay, true);
      overlay.setAttribute("aria-hidden", "true");
    }

    if (openButton) openButton.addEventListener("click", openModal);
    if (closeButton) closeButton.addEventListener("click", closeModal);
    if (overlay) {
      overlay.addEventListener("click", function (event) {
        if (event.target === overlay) closeModal();
      });
    }

    function handleAuthSuccess(data, sessionType, fallbackEmail) {
      state.token = data.token;
      state.user = data.user;
      state.email = (data.user && data.user.email) || fallbackEmail;
      state.sessionType = sessionType;
      state.loggedIn = true;
      state.currentView = "home";
      state.homeSurface = "avatar";
      render();
    }

    if (signInButton) {
      signInButton.addEventListener("click", function () {
        if (state.busy) return;
        toggleHidden(loginError, true);
        var email = emailInput && emailInput.value ? emailInput.value.trim() : "";
        var password = passwordInput && passwordInput.value ? passwordInput.value : "";
        if (!email || !password) {
          showError(loginError, "Enter your email and password.");
          return;
        }
        state.busy = true;
        bcfLogin(email, password).then(function (data) {
          state.busy = false;
          handleAuthSuccess(data, "signed_in", email);
        }).catch(function (err) {
          state.busy = false;
          showError(loginError, err.message);
        });
      });
    }

    if (guestButton) {
      guestButton.addEventListener("click", function () {
        if (state.busy) return;
        toggleHidden(loginError, true);
        state.busy = true;
        bcfGuestLogin().then(function (data) {
          state.busy = false;
          handleAuthSuccess(data, "guest", BCF_GUEST_EMAIL);
        }).catch(function (err) {
          state.busy = false;
          showError(loginError, err.message);
        });
      });
    }

    navButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.currentView = btn.getAttribute("data-view") || "home";
        render();
      });
    });

    avatarButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var avatarUrl = btn.getAttribute("data-avatar-url");
        if (!avatarUrl) return;

        state.selectedAvatar = avatarUrl;
        state.selectedAvatarFile = null;
        avatarButtons.forEach(function (node) {
          node.classList.toggle("is-active", node === btn);
        });
        render();
      });
    });

    if (uploadTrigger && uploadInput) {
      uploadTrigger.addEventListener("click", function () {
        uploadInput.click();
      });

      uploadInput.addEventListener("change", function () {
        var file = uploadInput.files && uploadInput.files[0];
        if (!file) return;

        state.selectedAvatarFile = file;

        var reader = new FileReader();
        reader.onload = function (event) {
          var result = event && event.target ? event.target.result : "";
          if (!result) return;
          state.selectedAvatar = String(result);
          avatarButtons.forEach(function (node) {
            node.classList.remove("is-active");
          });
          render();
        };
        reader.readAsDataURL(file);
      });
    }

    if (tryOnButton) {
      tryOnButton.addEventListener("click", function () {
        if (state.busy) return;
        toggleHidden(homeError, true);

        var selfiePromise = state.selectedAvatarFile
          ? Promise.resolve(state.selectedAvatarFile)
          : (state.selectedAvatar ? bcfUrlToFile(state.selectedAvatar, "avatar.png") : Promise.resolve(null));

        var garmentPromise = garmentImageUrl
          ? bcfUrlToFile(garmentImageUrl, "garment.jpg")
          : Promise.resolve(null);

        state.busy = true;
        setHomeSurface("loading");

        Promise.all([selfiePromise, garmentPromise]).then(function (files) {
          return bcfTryOnGemini(state.token, files[0], files[1]);
        }).then(function (resultObjectUrl) {
          state.busy = false;
          if (resultImage) resultImage.src = resultObjectUrl;
          setHomeSurface("result");
        }).catch(function (err) {
          state.busy = false;
          setHomeSurface("avatar");
          showError(homeError, err.message);
        });
      });
    }

    if (tryAgainButton) {
      tryAgainButton.addEventListener("click", function () {
        setHomeSurface("avatar");
      });
    }

    render();
  }

  var roots = document.querySelectorAll(".bcf-tryon-root[data-tryon-root]");
  roots.forEach(initializeTryOnRoot);
})();