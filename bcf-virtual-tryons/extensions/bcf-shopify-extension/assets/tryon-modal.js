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

  function bcfCreateAccount(payload) {
    return fetch(BCF_BACKEND_URL + "/api/create-account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().then(function (result) {
        if (!response.ok || !result.success) {
          throw new Error(result.error || "Account creation failed");
        }
        return result.data;
      });
    });
  }

  function bcfGetMeasurements(token) {
    return fetch(BCF_BACKEND_URL + "/api/body-measurements", {
      method: "GET",
      headers: bcfAuthHeaders(token)
    }).then(function (response) {
      return response.json().then(function (result) {
        if (!response.ok || !result.success) {
          throw new Error(result.error || "Could not load measurements");
        }
        return result.data;
      });
    });
  }

  function bcfCalculateAge(birthday) {
    if (!birthday) return "";
    var birthDate = new Date(birthday);
    if (isNaN(birthDate.getTime())) return "";
    var today = new Date();
    var age = today.getFullYear() - birthDate.getFullYear();
    var hasHadBirthdayThisYear = (today.getMonth() > birthDate.getMonth()) ||
      (today.getMonth() === birthDate.getMonth() && today.getDate() >= birthDate.getDate());
    if (!hasHadBirthdayThisYear) age -= 1;
    return age >= 0 ? String(age) : "";
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

  function bcfIsTransientNetworkError(err) {
    var message = err && err.message ? err.message : "";
    return message.indexOf("Failed to fetch") !== -1 || message.indexOf("NetworkError") !== -1;
  }

  function bcfWithRetry(fn, retries) {
    return fn().catch(function (err) {
      if (retries > 0 && bcfIsTransientNetworkError(err)) {
        return bcfWithRetry(fn, retries - 1);
      }
      throw err;
    });
  }

  function bcfTryOnGemini(token, avatarFile, garmentFile) {
    return bcfWithRetry(function () {
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
    }, 1);
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
    var signupView = root.querySelector('[data-tryon-view="signup"]');
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
    var heartButton = root.querySelector('[data-tryon-heart]');
    var homeError = root.querySelector('[data-tryon-home-error]');
    var tryAgainButton = root.querySelector('[data-tryon-reset]');
    var profileSession = root.querySelector('[data-profile-session]');
    var profileEmail = root.querySelector('[data-profile-email]');
    var profileFieldEls = root.querySelectorAll('[data-profile-field]');

    var signUpOpenButton = root.querySelector('[data-tryon-signup-open]');
    var signupSteps = root.querySelectorAll('[data-signup-step]');
    var signupProgressSegs = root.querySelectorAll('[data-signup-progress]');
    var signupBackButton = root.querySelector('[data-signup-back]');
    var signupNextButtons = root.querySelectorAll('[data-signup-next]');
    var signupSkipButton = root.querySelector('[data-signup-skip]');
    var signupSubmitButton = root.querySelector('[data-signup-submit]');
    var signupError = root.querySelector('[data-signup-error]');
    var signupEmailInput = root.querySelector('[data-signup-email]');
    var signupPasswordInput = root.querySelector('[data-signup-password]');
    var signupFirstNameInput = root.querySelector('[data-signup-first-name]');
    var signupLastNameInput = root.querySelector('[data-signup-last-name]');
    var signupGenderSelect = root.querySelector('[data-signup-gender]');
    var signupBirthdayInput = root.querySelector('[data-signup-birthday]');
    var signupStreetNameInput = root.querySelector('[data-signup-street-name]');
    var signupStreetNumberInput = root.querySelector('[data-signup-street-number]');
    var signupCityInput = root.querySelector('[data-signup-city]');
    var signupPostalCodeInput = root.querySelector('[data-signup-postal-code]');
    var signupMeasurementInputs = root.querySelectorAll('[data-signup-field]');

    var signupData = {};

    var garmentImageUrl = root.getAttribute("data-tryon-garment-image") || "";

    var state = {
      loggedIn: false,
      sessionType: "guest",
      email: "guest@example.com",
      token: null,
      user: null,
      measurements: null,
      currentView: "login",
      selectedAvatar: root.getAttribute("data-default-avatar") || "",
      selectedAvatarFile: null,
      busy: false,
      homeSurface: "avatar",
      signupStep: 1
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

    function updateProfileFields() {
      profileFieldEls.forEach(function (el) {
        var field = el.getAttribute("data-profile-field");
        var value = "";
        if (field === "age") {
          value = bcfCalculateAge(state.user && state.user.birthday);
        } else if (state.user && state.user[field]) {
          value = state.user[field];
        } else if (state.measurements && state.measurements[field]) {
          value = state.measurements[field];
        }
        el.textContent = value || value === 0 ? value : "Not set";
      });
    }

    function render() {
      var view = state.loggedIn ? state.currentView : (state.currentView === "signup" ? "signup" : "login");

      toggleHidden(loginView, view !== "login");
      toggleHidden(signupView, view !== "signup");
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

      updateProfileFields();

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

      bcfGetMeasurements(state.token).then(function (measurements) {
        state.measurements = measurements;
        updateProfileFields();
      }).catch(function () {
        state.measurements = null;
      });
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

    function getInputValue(el) {
      return el && el.value ? el.value.trim() : "";
    }

    function setSignupStep(stepNumber) {
      state.signupStep = stepNumber;
      signupSteps.forEach(function (stepEl) {
        toggleHidden(stepEl, stepEl.getAttribute("data-signup-step") !== String(stepNumber));
      });
      signupProgressSegs.forEach(function (seg) {
        var segNumber = parseInt(seg.getAttribute("data-signup-progress"), 10);
        seg.classList.toggle("is-active", segNumber <= stepNumber);
      });
    }

    if (signUpOpenButton) {
      signUpOpenButton.addEventListener("click", function () {
        signupData = {};
        toggleHidden(signupError, true);
        setSignupStep(1);
        state.currentView = "signup";
        render();
      });
    }

    if (signupBackButton) {
      signupBackButton.addEventListener("click", function () {
        if (state.signupStep > 1) {
          setSignupStep(state.signupStep - 1);
          return;
        }
        state.currentView = "login";
        render();
      });
    }

    signupNextButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var nextStep = parseInt(btn.getAttribute("data-signup-next"), 10);
        toggleHidden(signupError, true);

        if (state.signupStep === 1) {
          var email = getInputValue(signupEmailInput);
          var password = getInputValue(signupPasswordInput);
          if (!email || !password) {
            showError(signupError, "Enter your email and password.");
            return;
          }
          signupData.email = email;
          signupData.password = password;
          signupData.confirm_password = password;
        } else if (state.signupStep === 2) {
          var firstName = getInputValue(signupFirstNameInput);
          var lastName = getInputValue(signupLastNameInput);
          if (!firstName || !lastName) {
            showError(signupError, "Enter your first and last name.");
            return;
          }
          signupData.first_name = firstName;
          signupData.last_name = lastName;
          signupData.gender = getInputValue(signupGenderSelect);
          signupData.birthday = getInputValue(signupBirthdayInput);
        } else if (state.signupStep === 3) {
          var streetNumber = getInputValue(signupStreetNumberInput);
          var streetName = getInputValue(signupStreetNameInput);
          signupData.street = [streetNumber, streetName].filter(Boolean).join(" ").trim();
          signupData.city = getInputValue(signupCityInput);
          signupData.postal_code = getInputValue(signupPostalCodeInput);
        }

        setSignupStep(nextStep);
      });
    });

    function submitSignup(includeMeasurements) {
      if (state.busy) return;
      toggleHidden(signupError, true);

      var payload = Object.assign({}, signupData);
      if (includeMeasurements) {
        signupMeasurementInputs.forEach(function (input) {
          var field = input.getAttribute("data-signup-field");
          var value = getInputValue(input);
          if (field && value) payload[field] = value;
        });
      }

      state.busy = true;
      bcfCreateAccount(payload).then(function (data) {
        state.busy = false;
        handleAuthSuccess(data, "signed_in", payload.email);
      }).catch(function (err) {
        state.busy = false;
        showError(signupError, err.message);
      });
    }

    if (signupSkipButton) {
      signupSkipButton.addEventListener("click", function () {
        submitSignup(false);
      });
    }

    if (signupSubmitButton) {
      signupSubmitButton.addEventListener("click", function () {
        submitSignup(true);
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
          if (heartButton) {
            heartButton.classList.remove("is-liked");
            heartButton.setAttribute("aria-pressed", "false");
          }
          setHomeSurface("result");
        }).catch(function (err) {
          state.busy = false;
          setHomeSurface("avatar");
          showError(homeError, err.message);
        });
      });
    }

    if (heartButton) {
      heartButton.addEventListener("click", function () {
        var liked = heartButton.classList.toggle("is-liked");
        heartButton.setAttribute("aria-pressed", liked ? "true" : "false");
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