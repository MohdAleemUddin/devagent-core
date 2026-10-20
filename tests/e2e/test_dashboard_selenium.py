import os
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
import uvicorn
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.agent import executor as agent_executor
from app.agent import tools as agent_tools
from app.main import app


@pytest.fixture
def live_app(monkeypatch, tmp_path):
    async def controlled_agent(goal):
        if goal == "simulate agent failure":
            raise RuntimeError("private agent service details")
        return await agent_executor.run_react_agent(goal)

    async def fake_rag(question):
        if question == "simulate rag failure":
            raise RuntimeError("private RAG service details")
        return f"Answer: {question}"

    class FakeOllamaResponse:
        status_code = 200
        text = ""

        def __init__(self, content):
            self.content = content

        def json(self):
            return {"message": {"content": self.content}}

    class FakeOllamaClient:
        def __init__(self, **_kwargs):
            self.turn = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, **_kwargs):
            self.turn += 1
            if self.turn == 1:
                return FakeOllamaResponse(
                    "THOUGHT: Create the requested file.\n"
                    "TOOL: write_file(file_path='browser-created.md', "
                    "content='created by the real ReAct tool loop')"
                )
            return FakeOllamaResponse(
                "THOUGHT: The file was created.\n"
                "FINAL_ANSWER: Successfully created browser-created.md."
            )

    monkeypatch.setattr("app.main.run_react_agent", controlled_agent)
    monkeypatch.setattr("app.main.query_rag", fake_rag)
    monkeypatch.setattr(agent_executor.httpx, "AsyncClient", FakeOllamaClient)
    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", tmp_path)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="critical",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not thread.is_alive():
            pytest.fail("Uvicorn exited before the E2E test server was ready.")
        try:
            with urllib.request.urlopen(base_url, timeout=0.5) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("Timed out waiting for the E2E test server.")

    yield {"url": base_url, "created_file": tmp_path / "browser-created.md"}

    server.should_exit = True
    thread.join(timeout=10)
    if thread.is_alive():
        pytest.fail("E2E test server did not shut down cleanly.")


@pytest.fixture
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1100")
    if os.getenv("E2E_HEADLESS", "").lower() in {"1", "true", "yes"}:
        options.add_argument("--headless=new")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as chrome_error:
        edge_options = webdriver.EdgeOptions()
        edge_options.add_argument("--window-size=1440,1100")
        if os.getenv("E2E_HEADLESS", "").lower() in {"1", "true", "yes"}:
            edge_options.add_argument("--headless=new")
        try:
            driver = webdriver.Edge(options=edge_options)
        except WebDriverException as edge_error:
            pytest.skip(
                "Selenium could not start Chrome or Edge. Install a supported "
                "browser and allow Selenium Manager to resolve its driver. "
                f"Chrome: {chrome_error}; Edge: {edge_error}"
            )

    driver.set_page_load_timeout(15)
    yield driver
    driver.quit()


def wait_for_text(driver, element_id, expected_text):
    return WebDriverWait(driver, 5).until(
        lambda current_driver: expected_text
        in current_driver.find_element(By.ID, element_id).text
    )


def show_step(message):
    print(f"\n[E2E] {message}", flush=True)
    time.sleep(float(os.getenv("E2E_STEP_DELAY", "1.5")))


def test_dashboard_agent_and_rag_happy_edge_and_failure_flows(live_app, browser):
    print(f"\n[E2E] Browser opened. Dashboard URL: {live_app['url']}", flush=True)
    browser.get(live_app["url"])
    wait = WebDriverWait(browser, 10)

    assert "DevAgent Core" in browser.title
    assert wait.until(
        EC.visibility_of_element_located((By.ID, "agentGoal"))
    ).is_displayed()
    assert browser.find_element(By.ID, "ragQuestion").is_displayed()
    show_step("Dashboard loaded; Agent and RAG controls are visible.")

    agent_goal = browser.find_element(By.ID, "agentGoal")
    agent_output = browser.find_element(By.ID, "agentOutput")
    assert browser.find_elements(By.ID, "agentToken") == []
    assert browser.find_elements(By.XPATH, "//input[@type='password']") == []
    assert "window.prompt" not in browser.page_source

    browser.find_element(
        By.XPATH, "//button[contains(., 'Create doc file with write_file')]"
    ).click()
    assert "docs/about_project.md" in agent_goal.get_attribute("value")
    assert "Ollama, MCP, and pgvector" in agent_goal.get_attribute("value")
    agent_goal.clear()
    agent_goal.send_keys(
        "Use write_file to create browser-created.md with content "
        "created by the real ReAct tool loop"
    )
    show_step(
        "Clicked the Agent example, then entered a goal that the mocked model "
        "will fulfill by calling the real write_file tool."
    )

    browser.find_element(By.ID, "agentBtn").click()
    wait.until(
        lambda _driver: "Successfully created browser-created.md."
        in agent_output.get_attribute("textContent")
    )
    assert "Successfully created browser-created.md." in (
        agent_output.get_attribute("textContent")
    )
    assert live_app["created_file"].read_text(encoding="utf-8") == (
        "created by the real ReAct tool loop"
    )
    show_step(
        "Submitted the Agent goal; verified the real ReAct loop called write_file "
        "and created the expected file in a temporary test directory."
    )

    agent_goal.clear()
    agent_goal.send_keys("simulate agent failure")
    browser.find_element(By.ID, "agentBtn").click()
    wait_for_text(browser, "agentOutput", "Agent execution failed.")
    assert "private agent service details" not in agent_output.text
    show_step("Simulated Agent failure; verified a safe error is shown without private details.")

    question = browser.find_element(By.ID, "ragQuestion")
    rag_button = browser.find_element(By.ID, "ragBtn")
    rag_output = browser.find_element(By.ID, "ragOutput")

    browser.find_element(
        By.XPATH, "//button[contains(., 'Ask about project stack')]"
    ).click()
    assert question.get_attribute("value") == "What is this project built using?"
    show_step("Clicked the RAG example; verified it populated the question field.")
    rag_button.click()
    wait.until(
        lambda _driver: "Answer:" in rag_output.get_attribute("textContent")
    )
    show_step("Submitted the RAG question; verified the answer appears.")

    question.clear()
    question.send_keys("simulate rag failure")
    rag_button.click()
    wait_for_text(browser, "ragOutput", "RAG query failed.")
    assert "private RAG service details" not in rag_output.text
    show_step("Simulated RAG failure; verified a safe error is shown without private details.")

    question.clear()
    rag_button.click()
    alert = wait.until(EC.alert_is_present())
    assert "Please enter a question" in alert.text
    alert.accept()
    show_step("Clicked RAG with an empty question; verified client-side validation.")

    invalid_request_status = browser.execute_async_script(
        """
        const done = arguments[0];
        fetch('/api/rag/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({question: []})
        }).then(response => done(response.status))
          .catch(() => done(0));
        """
    )
    assert invalid_request_status == 422
    show_step("Submitted malformed question data; verified the API rejects it with HTTP 422.")

    hold_seconds = float(os.getenv("E2E_HOLD_SECONDS", "8"))
    print(
        f"\n[E2E] All browser checks passed. Keeping the browser open for "
        f"{hold_seconds:g} seconds before closing.",
        flush=True,
    )
    time.sleep(hold_seconds)
