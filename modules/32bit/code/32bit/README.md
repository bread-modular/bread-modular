## 32bit firmwares

This is the main firmware source code for the 32bit.

## Building Firmwares

Run the following script in an esp-idf terminal.

```
python3 scripts/make_installer.py
```

Then it will generate a set of packages in the `dist` directory. The version name is taken from `../../VERSION`.

## Uploading Firmwares

We host these firmwares in Vercel blobs. This is the public url: https://gmeozbt7rg290j7h.public.blob.vercel-storage.com

* Visit the vercel [blob browser](https://vercel.com/arunoda-susiripalas-projects-de86cc77/website/stores/blob/store_gMeoZbT7rG290j7h/browser)
* Then simply drag and drop the directories 
* Then make sure to update `index.txt` with all the directories (or firmwares) in the blob

> Based on this, [32bit UI](https://www.breadmodular.com/ui/32bit/install) will automatically list these firmwares and users can install them.
