// Compare against a known successful/develop base, not Jenkins' previous job-wide changelog.
def selectCiComponents(String baseCommit) {
    def allComponents = [backend: true, frontend: true, keyfinPay: true]
    if (!(baseCommit ==~ /[0-9a-fA-F]{40}/)) {
        echo 'No comparison baseline is available; validating every application.'
        return allComponents
    }

    return withEnv(["CI_DIFF_BASE=${baseCommit}"]) {
        if (sh(script: 'git merge-base --is-ancestor "$CI_DIFF_BASE" HEAD',
               returnStatus: true) != 0) {
            echo 'The baseline is unavailable or not an ancestor; validating every application.'
            return allComponents
        }

        // Disable rename detection so moves between applications select both sides.
        def paths = sh(
            script: 'git -c core.quotepath=false diff --no-renames --name-only "$CI_DIFF_BASE" HEAD --',
            returnStdout: true
        ).readLines()
        def sharedChange = paths.any { path ->
            !path.startsWith('backend/') && !path.startsWith('frontend/') &&
            !path.startsWith('ai/') && !path.startsWith('docs/') &&
            !path.startsWith('keyfin-pay/') &&
            !path.startsWith('.gitlab/merge_request_templates/') && path != 'README.md'
        }

        return [
            backend: sharedChange || paths.any { it.startsWith('backend/') },
            frontend: sharedChange || paths.any { it.startsWith('frontend/') },
            keyfinPay: sharedChange || paths.any { it.startsWith('keyfin-pay/') }
        ]
    }
}

// Use the agent's existing Docker daemon; Node/pnpm are only needed inside this image.
def checkFrontend() {
    writeFile file: '.ci-frontend.Dockerfile', text: '''
FROM node:24-bookworm-slim
ENV CI=true COREPACK_ENABLE_DOWNLOAD_PROMPT=0 EXPO_NO_TELEMETRY=1
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG CI_RUN_ID
RUN echo "CI run: $CI_RUN_ID" && pnpm run typecheck
RUN pnpm run lint
RUN pnpm test --ci --runInBand
'''
    // Cache dependency installation, but execute the checks again for each Jenkins build.
    sh 'docker build --build-arg "CI_RUN_ID=$BUILD_TAG" --file .ci-frontend.Dockerfile frontend'
}

// keyfin-pay runs on the Node test runner only; no toolchain is needed on the agent itself.
def checkKeyfinPay() {
    writeFile file: '.ci-keyfin-pay.Dockerfile', text: '''
FROM node:22-alpine
ENV CI=true
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG CI_RUN_ID
RUN echo "CI run: $CI_RUN_ID" && npm test
'''
    sh 'docker build --build-arg "CI_RUN_ID=$BUILD_TAG" --file .ci-keyfin-pay.Dockerfile keyfin-pay'
}

pipeline {
    agent { label 'backend-ci' }

    environment {
        // The workspace is wiped every build; keep Gradle's dependency and build caches on the persistent agent volume.
        GRADLE_USER_HOME = '/home/jenkins/agent/.gradle'
    }

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        skipStagesAfterUnstable()
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {
        stage('Checkout') {
            steps {
                // Start with a clean workspace so old reports cannot be published.
                deleteDir()
                // Repository, branch and credentials come from the Jenkins job's SCM settings.
                script {
                    def checkoutInfo = checkout scm
                    env.CI_BASE_COMMIT = checkoutInfo.GIT_PREVIOUS_SUCCESSFUL_COMMIT ?: ''
                    env.CI_COMMIT = checkoutInfo.GIT_COMMIT
                }
                sh 'git log -1 --format="%H %s"'
            }
        }

        stage('Select Changed Applications') {
            steps {
                script {
                    def components = selectCiComponents(env.CI_BASE_COMMIT)
                    env.CI_RUN_BACKEND = components.backend.toString()
                    env.CI_RUN_FRONTEND = components.frontend.toString()
                    env.CI_RUN_KEYFIN_PAY = components.keyfinPay.toString()
                    echo "Backend: ${env.CI_RUN_BACKEND}; frontend: ${env.CI_RUN_FRONTEND}; " +
                         "keyfin-pay: ${env.CI_RUN_KEYFIN_PAY}"
                }
            }
        }

        stage('Backend Environment Check') {
            when { expression { env.CI_RUN_BACKEND == 'true' } }
            steps {
                sh '''
                    set -eu
                    echo "Node: $NODE_NAME"
                    java -version
                    javac -version
                    git --version
                    test -S /var/run/docker.sock
                    test -r /var/run/docker.sock
                    test -w /var/run/docker.sock
                '''
            }
        }

        stage('Backend Test') {
            when { expression { env.CI_RUN_BACKEND == 'true' } }
            steps {
                dir('backend/key-fin') {
                    sh 'bash ./gradlew --max-workers=2 --build-cache --console=plain --stacktrace test --rerun'
                }
            }
            post {
                always {
                    junit testResults: 'backend/key-fin/build/test-results/test/*.xml', allowEmptyResults: false
                }
            }
        }

        stage('Frontend Checks') {
            when { expression { env.CI_RUN_FRONTEND == 'true' } }
            steps {
                script { checkFrontend() }
            }
        }

        stage('keyfin-pay Checks') {
            when { expression { env.CI_RUN_KEYFIN_PAY == 'true' } }
            steps {
                script { checkKeyfinPay() }
            }
        }

        stage('Package JAR') {
            when { expression { env.CI_RUN_BACKEND == 'true' } }
            steps {
                dir('backend/key-fin') {
                    sh 'bash ./gradlew --max-workers=2 --build-cache --console=plain --stacktrace bootJar'
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'backend/key-fin/build/libs/*.jar',
                                    fingerprint: true
                }
            }
        }

        stage('Build Docker Image') {
            when { expression { env.CI_RUN_BACKEND == 'true' } }
            steps {
                script {
                    env.CI_COMMIT = sh(
                        script: 'git rev-parse HEAD',
                        returnStdout: true
                    ).trim()

                    env.APP_IMAGE =
                        "keyfin-backend:ci-${env.BUILD_NUMBER}-${env.CI_COMMIT.take(12)}"
                }

                sh '''
                    set -eu

                    mkdir -p .ci-image
                    jar_count=0

                    for jar_file in backend/key-fin/build/libs/*.jar; do
                        [ -f "$jar_file" ] || continue

                        case "$jar_file" in
                            *-plain.jar) continue ;;
                        esac

                        cp "$jar_file" .ci-image/app.jar
                        jar_count=$((jar_count + 1))
                    done

                    test "$jar_count" -eq 1

                    cp backend/key-fin/Dockerfile.runtime .ci-image/Dockerfile

                    docker build \
                        --label "org.opencontainers.image.revision=$CI_COMMIT" \
                        -t "$APP_IMAGE" .ci-image
                '''
            }
        }

        stage('Deploy Backend') {
            when { expression { env.CI_RUN_BACKEND == 'true' } }
            steps {
                sh '''
                    set -eu

                    test "$(git rev-parse HEAD)" = \
                        "$(git rev-parse refs/remotes/origin/develop)"

                    bash infra/jenkins/deploy-backend.sh "$APP_IMAGE"
                '''
                script { env.CI_BACKEND_DEPLOYED = 'true' }
            }
        }

        stage('Build keyfin-pay Image') {
            when { expression { env.CI_RUN_KEYFIN_PAY == 'true' } }
            steps {
                script {
                    env.CI_COMMIT = sh(
                        script: 'git rev-parse HEAD',
                        returnStdout: true
                    ).trim()

                    env.KEYFIN_PAY_IMAGE =
                        "keyfin-pay:ci-${env.BUILD_NUMBER}-${env.CI_COMMIT.take(12)}"
                }

                sh '''
                    set -eu

                    docker build \
                        --label "org.opencontainers.image.revision=$CI_COMMIT" \
                        -t "$KEYFIN_PAY_IMAGE" keyfin-pay
                '''
            }
        }

        stage('Deploy keyfin-pay') {
            when { expression { env.CI_RUN_KEYFIN_PAY == 'true' } }
            steps {
                sh '''
                    set -eu

                    test "$(git rev-parse HEAD)" = \
                        "$(git rev-parse refs/remotes/origin/develop)"

                    bash infra/jenkins/deploy-keyfin-pay.sh "$KEYFIN_PAY_IMAGE"
                '''
                script { env.CI_KEYFIN_PAY_DEPLOYED = 'true' }
            }
        }
    }

    post {
        always {
            script {
                def result = currentBuild.currentResult

                def deployed = []
                if (env.CI_BACKEND_DEPLOYED == 'true') { deployed << '백엔드' }
                if (env.CI_KEYFIN_PAY_DEPLOYED == 'true') { deployed << 'keyfin-pay' }

                def notifications = [
                    SUCCESS: [
                        color: 'good',
                        title: deployed
                            ? "✅ CI 검증·${deployed.join('·')} 배포 성공"
                            : '✅ CI 검증 완료 (배포 없음)'
                    ],
                    FAILURE: [
                        color: 'danger',
                        title: '❌ CI/CD 파이프라인 실패 — 로그 확인 필요'
                    ],
                    UNSTABLE: [
                        color: 'warning',
                        title: '⚠️ CI/CD 파이프라인 불안정 — 테스트 결과 확인 필요'
                    ],
                    ABORTED: [
                        color: '#808080',
                        title: '⏹️ CI/CD 파이프라인 중단'
                    ]
                ]

                def notification = notifications[result] ?: [
                    color: '#808080',
                    title: "ℹ️ CI/CD 파이프라인 종료: ${result}"
                ]

                def branch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: '확인 불가'
                def commit = env.CI_COMMIT ?: env.GIT_COMMIT
                def shortCommit = commit ? commit.take(8) : '확인 불가'

                def message = [
                    "**${notification.title}**",
                    "작업: ${env.JOB_NAME} · 빌드: #${env.BUILD_NUMBER}",
                    "브랜치: ${branch} · 커밋: ${shortCommit}",
                    "검증 대상 — 백엔드: ${env.CI_RUN_BACKEND ?: '미확인'} · 프론트엔드: ${env.CI_RUN_FRONTEND ?: '미확인'} · keyfin-pay: ${env.CI_RUN_KEYFIN_PAY ?: '미확인'}",
                    "[실행 결과](${env.BUILD_URL}) · [콘솔 로그](${env.BUILD_URL}console)"
                ].join('\n')

                mattermostSend(
                    color: notification.color,
                    message: message,
                    failOnError: false
                )
            }
        }
    }
}
