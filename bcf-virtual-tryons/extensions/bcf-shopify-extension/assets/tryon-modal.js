(function () {
  var BCF_BACKEND_URL = "https://server.becausefuture.tech";
  var BCF_GUEST_EMAIL = "dev@enableyou.co";
  var BCF_GUEST_PASSWORD = "BFDemo2026!Review";
  var BCF_GUEST_2FA_CODE = "123456";

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
    return bcfLogin(BCF_GUEST_EMAIL, BCF_GUEST_PASSWORD).then(function (data) {
      if (!data.requires_2fa) {
        return data;
      }

      return fetch(BCF_BACKEND_URL + "/api/verify-2fa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: BCF_GUEST_EMAIL,
          code: BCF_GUEST_2FA_CODE
        })
      }).then(function (response) {
        return response.json().then(function (result) {
          if (!response.ok || !result.success) {
            throw new Error(result.error || "2FA verification failed");
          }
          return result.data;
        });
      });
    });
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
    }).then(bcfRejectExpiredToken).then(function (response) {
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

  var BCF_SESSION_STORAGE_KEY = "bcf_tryon_session";

  function bcfClearSession() {
    try {
      window.localStorage.removeItem(BCF_SESSION_STORAGE_KEY);
    } catch (err) {
      // Storage unavailable.
    }
  }

  function bcfSaveSession(session) {
    try {
      window.localStorage.setItem(BCF_SESSION_STORAGE_KEY, JSON.stringify(session));
    } catch (err) {
      // Storage unavailable (private mode, etc.) - session just won't persist.
    }
  }

  function bcfLoadSession() {
    try {
      var raw = window.localStorage.getItem(BCF_SESSION_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function bcfRejectExpiredToken(response) {
    if (response.status === 401) {
      bcfClearSession();
    }
    return response;
  }

  var BCF_TRYON_CHAIN_STORAGE_KEY = "bcf_tryon_chain";

  function bcfSaveTryonChain(chain) {
    try {
      window.sessionStorage.setItem(BCF_TRYON_CHAIN_STORAGE_KEY, JSON.stringify(chain));
    } catch (err) {
      // Storage unavailable or image too large - chain just won't carry over pages.
    }
  }

  function bcfLoadTryonChain() {
    try {
      var raw = window.sessionStorage.getItem(BCF_TRYON_CHAIN_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function bcfClearTryonChain() {
    try {
      window.sessionStorage.removeItem(BCF_TRYON_CHAIN_STORAGE_KEY);
    } catch (err) {
      // ignore
    }
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
      }).then(bcfRejectExpiredToken).then(function (response) {
        if (!response.ok) {
          return response.json().then(function (result) {
            throw new Error(result.error || "Try-on failed");
          });
        }
        return response.blob().then(bcfBlobToDataUrl);
      });
    }, 1);
  }

  function bcfBlobToDataUrl(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        resolve(String(reader.result));
      };
      reader.onerror = function () {
        reject(reader.error || new Error("Could not read image"));
      };
      reader.readAsDataURL(blob);
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
      baseAvatar: root.getAttribute("data-default-avatar") || "",
      baseAvatarFile: null,
      tryonCount: 0,
      busy: false,
      homeSurface: "avatar",
      signupStep: 1
    };

    var savedSession = bcfLoadSession();
    if (savedSession && savedSession.token) {
      state.token = savedSession.token;
      state.user = savedSession.user;
      state.email = savedSession.email || state.email;
      state.sessionType = savedSession.sessionType || "guest";
      state.loggedIn = true;
      state.currentView = "home";
      state.homeSurface = "avatar";
    }

    // Carries a chained try-on avatar (e.g. a t-shirt result) across product pages
    // so a second garment (e.g. trousers) can be tried on top of it.
    var savedChain = bcfLoadTryonChain();
    if (savedChain && savedChain.selectedAvatar) {
      state.selectedAvatar = savedChain.selectedAvatar;
      state.baseAvatar = savedChain.baseAvatar || state.baseAvatar;
      state.tryonCount = savedChain.tryonCount || 0;
    }

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

    var rootOriginalParent = root.parentNode;
    var rootOriginalNextSibling = root.nextSibling;

    function openModal() {
      // Move the whole root to <body> so the fixed overlay can't be clipped/hidden
      // by an ancestor's stacking context (e.g. a sticky/transformed header).
      if (root.parentNode !== document.body) {
        document.body.appendChild(root);
      }
      toggleHidden(overlay, false);
      overlay.setAttribute("aria-hidden", "false");
      render();
    }

    function closeModal() {
      toggleHidden(overlay, true);
      overlay.setAttribute("aria-hidden", "true");
      if (root.parentNode === document.body && rootOriginalParent) {
        if (rootOriginalNextSibling && rootOriginalNextSibling.parentNode === rootOriginalParent) {
          rootOriginalParent.insertBefore(root, rootOriginalNextSibling);
        } else {
          rootOriginalParent.appendChild(root);
        }
      }
    }

    if (openButton) {
      function stopImageInteraction(event) {
        event.stopPropagation();
        event.stopImmediatePropagation();
      }

      openButton.addEventListener("pointerdown", stopImageInteraction, true);
      openButton.addEventListener("mousedown", stopImageInteraction, true);
      openButton.addEventListener("touchstart", stopImageInteraction, true);
      openButton.addEventListener("pointerup", stopImageInteraction, true);
      openButton.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        openModal();
      }, true);
      openButton.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    }
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
      bcfSaveSession({
        token: state.token,
        user: state.user,
        email: state.email,
        sessionType: state.sessionType
      });
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
        state.baseAvatar = avatarUrl;
        state.baseAvatarFile = null;
        state.tryonCount = 0;
        bcfClearTryonChain();
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
        state.baseAvatarFile = file;
        state.tryonCount = 0;

        var reader = new FileReader();
        reader.onload = function (event) {
          var result = event && event.target ? event.target.result : "";
          if (!result) return;
          state.selectedAvatar = String(result);
          state.baseAvatar = String(result);
          bcfClearTryonChain();
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

        // After two chained try-ons in a row, start over from the original avatar image.
        if (state.tryonCount >= 2) {
          state.tryonCount = 0;
          state.selectedAvatar = state.baseAvatar;
          state.selectedAvatarFile = state.baseAvatarFile;
          bcfClearTryonChain();
        }

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
          state.tryonCount += 1;
          // Chain: use this result as the avatar input for the next try-on.
          state.selectedAvatar = resultObjectUrl;
          state.selectedAvatarFile = null;
          bcfSaveTryonChain({
            selectedAvatar: state.selectedAvatar,
            baseAvatar: state.baseAvatar,
            tryonCount: state.tryonCount
          });
          avatarPreviewImages.forEach(function (img) {
            img.src = state.selectedAvatar;
          });
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
        render();
        setHomeSurface("avatar");
      });
    }

    if (state.loggedIn && state.token) {
      bcfGetMeasurements(state.token).then(function (measurements) {
        state.measurements = measurements;
        updateProfileFields();
      }).catch(function () {
        state.measurements = null;
      });
    }

    render();
  }

  function moveTryOnRootToProductMedia(root) {
    var productMedia;
    var productImageUrl = root.getAttribute("data-tryon-garment-image") || "";
    var imagePath = productImageUrl.split("?")[0].split("/").pop();
    var imageCandidates = document.querySelectorAll("img");

    imageCandidates.forEach(function (image) {
      if (productMedia || image.closest(".bcf-tryon-root")) {
        return;
      }

      var imageSrc = image.currentSrc || image.src || "";
      var isProductImage = imagePath && imageSrc.indexOf(imagePath) !== -1;

      if (isProductImage) {
        productMedia = image.closest(
          ".product__media-item, .product-gallery__media, .product-media-container, " +
          ".media, [data-media-id]"
        ) || image.parentElement;
      }
    });

    if (!productMedia) {
      productMedia = document.querySelector(
        ".product__media-wrapper, .product__media, media-gallery, product-gallery, " +
        ".product-gallery, [data-product-media-wrapper]"
      );
    }

    if (!productMedia) {
      return;
    }

    if (root.parentNode !== document.body) {
      document.body.appendChild(root);
    }

    var mediaRect = productMedia.getBoundingClientRect();
    var rootWidth = root.getBoundingClientRect().width;

    if (!mediaRect.width || !mediaRect.height) {
      return;
    }

    root.style.setProperty("position", "fixed", "important");
    root.style.setProperty("top", Math.max(8, mediaRect.top + 12) + "px", "important");
    root.style.setProperty("left", Math.max(8, mediaRect.right - rootWidth - 12) + "px", "important");
    root.style.setProperty("right", "auto", "important");
    root.style.setProperty("display", "block", "important");
    root.style.setProperty("visibility", "visible", "important");
    root.style.setProperty("opacity", "1", "important");
  }

  function positionTryOnRoots() {
    var roots = document.querySelectorAll(".bcf-tryon-root[data-tryon-root]");
    roots.forEach(function (root) {
      moveTryOnRootToProductMedia(root);
      initializeTryOnRoot(root);
    });
  }

  positionTryOnRoots();
  document.addEventListener("shopify:section:load", positionTryOnRoots);
  window.addEventListener("resize", positionTryOnRoots);
  window.addEventListener("scroll", positionTryOnRoots, true);
  window.addEventListener("load", positionTryOnRoots);

  if (window.MutationObserver) {
    new MutationObserver(positionTryOnRoots).observe(document.body, {
      childList: true,
      subtree: true
    });
  }
})();