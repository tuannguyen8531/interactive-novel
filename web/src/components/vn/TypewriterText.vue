<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(
  defineProps<{
    text: string
    speed?: number
    animate?: boolean
  }>(),
  {
    speed: 18,
    animate: true
  }
)

const emit = defineEmits<{
  (event: 'tick', char: string): void
  (event: 'finish'): void
}>()

const displayedText = ref('')
const isTyping = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

function startTyping(): void {
  if (timer) clearTimeout(timer)
  if (!props.animate) {
    displayedText.value = props.text
    isTyping.value = false
    emit('finish')
    return
  }

  displayedText.value = ''
  isTyping.value = true
  let index = 0

  function typeNext(): void {
    if (index < props.text.length) {
      displayedText.value += props.text.charAt(index)
      index += 1
      emit('tick', props.text.charAt(index - 1))
      timer = setTimeout(typeNext, props.speed)
    } else {
      isTyping.value = false
      emit('finish')
    }
  }

  typeNext()
}

function skip(): void {
  if (timer) clearTimeout(timer)
  displayedText.value = props.text
  isTyping.value = false
  emit('finish')
}

watch(
  () => props.text,
  () => {
    startTyping()
  }
)

onMounted(() => {
  startTyping()
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <div class="typewriter-container" @click="isTyping ? skip() : null">
    <span class="typewriter-content">{{ displayedText }}</span>
    <span v-if="isTyping" class="typewriter-cursor">▎</span>
  </div>
</template>

<style scoped>
.typewriter-container {
  font-size: 1.05rem;
  line-height: 1.75;
  color: #e2e8f0;
  cursor: pointer;
  user-select: text;
  white-space: pre-wrap;
  word-break: break-word;
}

.typewriter-content {
  letter-spacing: 0.01em;
}

.typewriter-cursor {
  display: inline-block;
  color: #6366f1;
  font-weight: 700;
  margin-left: 2px;
  animation: blink 0.8s infinite;
  vertical-align: baseline;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
