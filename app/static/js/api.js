async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options,
    });

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        const message =
            data?.detail ||
            "요청을 처리하지 못했습니다.";

        throw new Error(message);
    }

    return data;
}


async function apiGet(url) {
    return apiRequest(url);
}


async function apiPost(url, body = null) {
    return apiRequest(url, {
        method: "POST",
        body,
    });
}


async function apiDelete(url) {
    return apiRequest(url, {
        method: "DELETE",
    });
}