from tqdm import tqdm
import time
import torch
import evaluate 
from datasets import load_dataset, Audio
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, AutoModelForCausalLM


import sys
sys.path.append('/exp/whisper_yue/finetune-whisper-canto')

from normalize_canto import normalize


metric = evaluate.load("cer")

device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32


def assisted_generate_with_time(model, inputs, **kwargs):
    start_time = time.time()
    outputs = model.generate(**inputs, **kwargs)
    generation_time = time.time() - start_time
    return outputs, generation_time


if __name__ == "__main__":
    dataset = load_dataset("mozilla-foundation/common_voice_16_0", "yue", split="test", use_auth_token=True)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=16_000))

    model_id = "simonl0909/whisper-large-v2-cantonese"
    model_id = "/exp/whisper_yue/finetune-whisper-canto/distil-whisper/distilled_boi_01/"
    # model_id = "/exp/whisper_yue/finetune-whisper-canto/model_out/checkpoint-15000"
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
        # attn_implementation="sdpa",
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(model_id)

    all_time = 0
    predictions = []
    references = []

    for sample in tqdm(dataset):
        audio = sample["audio"]
        inputs = processor(audio["array"], sampling_rate=16_000, return_tensors="pt")
        inputs = inputs.to(device=device, dtype=torch_dtype)
        
        output, gen_time = assisted_generate_with_time(model, inputs)
        all_time += gen_time
        pred = processor.batch_decode(output, skip_special_tokens=True)[0]
        pred = normalize(pred)
        predictions.append(pred)
        
        references.append(normalize(sample["sentence"]))
        
    print(f"took {all_time} for {len(references)} samples on GPU")
    cer = metric.compute(references=references, predictions=predictions)
    cer = round(100 * cer, 2)
    print(cer)
